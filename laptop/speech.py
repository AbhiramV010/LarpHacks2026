"""Push-to-talk mic capture -> faster-whisper STT; TTS via ElevenLabs, falling back to Windows SAPI."""
import logging
import os
import queue
import subprocess
import tempfile
import threading
import time
import wave

import numpy as np
import requests
import sounddevice as sd
import config

log = logging.getLogger("speech")
RATE = 16000
FRAME = 480                       # 30 ms
MIN_CLIP_S = 0.6                  # shorter holds are ignored


class Listener:
    """Records the mic only while the push-to-talk key is held.
    Emits ("audio", ndarray) on release, or ("cancel", None) for a tap too short to use."""

    def __init__(self, on_level):
        self.events = queue.Queue()
        self.on_level = on_level      # callable(rms, recording), throttled here
        self.ok = True
        self._frames = queue.Queue()
        self._recording = threading.Event()
        self._buf = []
        self._released = False

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def ptt_press(self):
        self._buf = []
        self._recording.set()

    def ptt_release(self):
        self._recording.clear()
        self._released = True

    def _callback(self, indata, frames, t, status):
        self._frames.put(indata[:, 0].copy())

    def _run(self):
        try:
            stream = sd.InputStream(samplerate=RATE, channels=1, dtype="float32",
                                    blocksize=FRAME, callback=self._callback)
            stream.start()
        except Exception as e:
            log.error("Mic open failed: %s", e)
            self.ok = False
            return

        last_level = 0.0
        while True:
            frame = self._frames.get()
            now = time.time()
            if now - last_level > 0.1:
                self.on_level(float(np.sqrt(np.mean(frame ** 2))), self._recording.is_set())
                last_level = now
            if self._recording.is_set():
                self._buf.append(frame)
            elif self._released:
                self._released = False
                audio = np.concatenate(self._buf) if self._buf else np.zeros(0, np.float32)
                self._buf = []
                self.events.put(("audio", audio) if len(audio) / RATE >= MIN_CLIP_S else ("cancel", None))


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
