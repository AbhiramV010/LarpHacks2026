"""Always-on listener (numpy VAD) -> faster-whisper STT; TTS via ElevenLabs, falling back to Windows SAPI."""
import logging
import os
import queue
import subprocess
import tempfile
import threading
import time
import wave
from collections import deque

import numpy as np
import requests
import sounddevice as sd
import config

log = logging.getLogger("speech")
RATE = 16000
FRAME = 480                       # 30 ms
SPEECH_START_S = 0.6              # above-threshold time needed to start
SPEECH_END_S = 0.8                # below-threshold time that ends an utterance
PRE_ROLL_S = 0.3                  # audio kept from before the start
CALIBRATE_S = 2.0
MAX_UTTERANCE_S = 30.0


class Listener:
    """Thread that turns the mic into utterances. Puts (speech_started) and (audio) events on `events`."""

    def __init__(self, is_muted, on_level):
        self.events = queue.Queue()     # ("start", None) | ("audio", np.ndarray)
        self.is_muted = is_muted        # callable -> True while the duck is talking/typing/translating
        self.on_level = on_level        # callable(rms, threshold), throttled by caller
        self.threshold = 0.0
        self.ok = True
        self._recalibrate = threading.Event()
        self._frames = queue.Queue()
        self._recalibrate.set()         # calibrate on startup
        self._ptt = threading.Event()   # held push-to-talk key
        self._ptt_buf = []
        self._ptt_released = False

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def recalibrate(self):
        self._recalibrate.set()

    def ptt_press(self):
        self._ptt_buf = []
        self._ptt.set()

    def ptt_release(self):
        self._ptt.clear()
        self._ptt_released = True

    def _callback(self, indata, frames, t, status):
        self._frames.put(indata[:, 0].copy())

    def _read(self):
        return self._frames.get()

    def _run(self):
        try:
            stream = sd.InputStream(samplerate=RATE, channels=1, dtype="float32",
                                    blocksize=FRAME, callback=self._callback)
            stream.start()
        except Exception as e:
            log.error("Mic open failed: %s", e)
            self.ok = False
            return

        pre = deque(maxlen=int(PRE_ROLL_S * RATE / FRAME))
        speaking = False
        above = 0
        below = 0
        chunk = []
        last_level = 0.0
        while True:
            if self._recalibrate.is_set():
                self._calibrate()
                self._recalibrate.clear()
                pre.clear()
                speaking, above, below, chunk = False, 0, 0, []
                continue

            frame = self._read()
            rms = float(np.sqrt(np.mean(frame ** 2)))
            now = time.time()
            if now - last_level > 0.1:
                self.on_level(rms, self.threshold)
                last_level = now

            if self._ptt.is_set():        # held key: record everything, no VAD
                self._ptt_buf.append(frame)
                continue
            if self._ptt_released:
                self._ptt_released = False
                audio = np.concatenate(self._ptt_buf) if self._ptt_buf else np.zeros(0, np.float32)
                self._ptt_buf = []
                self.events.put(("audio", audio) if len(audio) / RATE >= 0.6 else ("cancel", None))
                continue
            if self.is_muted():           # self-hearing guard: drop everything
                pre.clear()
                speaking, above, below, chunk = False, 0, 0, []
                continue

            loud = rms > self.threshold
            if not speaking:
                pre.append(frame)
                above = above + 1 if loud else 0
                if above * FRAME / RATE >= SPEECH_START_S:
                    speaking = True
                    below = 0
                    chunk = list(pre)
                    self.events.put(("start", None))
                continue

            chunk.append(frame)
            below = 0 if loud else below + 1
            too_long = len(chunk) * FRAME / RATE > MAX_UTTERANCE_S
            if below * FRAME / RATE >= SPEECH_END_S or too_long:
                audio = np.concatenate(chunk)
                speaking, above, below, chunk = False, 0, 0, []
                pre.clear()
                if len(audio) / RATE >= 0.6:
                    self.events.put(("audio", audio))
                else:
                    self.events.put(("cancel", None))

    def _calibrate(self):
        n = int(CALIBRATE_S * RATE / FRAME)
        levels = [float(np.sqrt(np.mean(self._read() ** 2))) for _ in range(n)]
        noise = float(np.sqrt(np.mean(np.square(levels))))
        self.threshold = max(3.0 * noise, 0.005)
        log.info("Noise floor %.4f, speech threshold %.4f", noise, self.threshold)


class STT:
    def __init__(self):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
        log.info("Whisper %s loaded", config.WHISPER_MODEL)

    def transcribe(self, audio):
        segments, _ = self.model.transcribe(audio, language="en", vad_filter=True, beam_size=1)
        return " ".join(s.text.strip() for s in segments).strip()


class TTS:
    def __init__(self):
        self.key = os.environ.get("ELEVENLABS_API_KEY", "")
        self.use_eleven = bool(self.key)
        if not self.key:
            log.warning("ELEVENLABS_API_KEY not set; using Windows SAPI voice")

    def _eleven(self, text):
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}",
            params={"output_format": "pcm_16000"},
            headers={"xi-api-key": self.key},
            json={"text": text, "model_id": config.ELEVENLABS_MODEL}, timeout=15)
        r.raise_for_status()
        return np.frombuffer(r.content, dtype=np.int16), 16000

    def _sapi(self, text):
        path = os.path.join(tempfile.gettempdir(), "duck_say.wav")
        ps = ("Add-Type -AssemblyName System.Speech; "
              "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"$s.SetOutputToWaveFile('{path}'); $s.Rate = 1; "
              "$s.Speak([Console]::In.ReadToEnd()); $s.Dispose()")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], input=text.encode("utf-8"),
                       timeout=30, check=True, capture_output=True)
        with wave.open(path, "rb") as w:
            frames = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
            if w.getnchannels() == 2:
                frames = frames[::2]
            return frames, w.getframerate()

    def say(self, text):
        """Blocks until playback finishes (or sd.stop() is called)."""
        if not text:
            return
        audio = None
        if self.use_eleven:
            try:
                audio, rate = self._eleven(text)
            except Exception as e:
                log.warning("ElevenLabs failed (%s); falling back to SAPI", e)
        if audio is None:
            try:
                audio, rate = self._sapi(text)
            except Exception as e:
                log.error("SAPI TTS failed: %s", e)
                return
        sd.play(audio, rate, blocking=True)

    @staticmethod
    def stop():
        sd.stop()
