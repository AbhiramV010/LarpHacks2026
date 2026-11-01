"""STT with faster-whisper; TTS with ElevenLabs, falling back to the Windows SAPI voice."""
import logging
import os
import subprocess
import tempfile
import threading
import wave

import numpy as np
import requests
import sounddevice as sd
import config

log = logging.getLogger("speech")
RATE = 16000


class Recorder:
    def __init__(self):
        self._chunks = []
        self._stream = None
        self._lock = threading.Lock()
        self.ok = True

    def start(self):
        with self._lock:
            self._chunks = []
            try:
                self._stream = sd.InputStream(samplerate=RATE, channels=1, dtype="int16",
                                              callback=lambda d, f, t, s: self._chunks.append(d.copy()))
                self._stream.start()
                self.ok = True
            except Exception as e:
                log.error("Mic open failed: %s", e)
                self.ok = False
                self._stream = None

    def stop(self):
        """Returns float32 mono audio at 16 kHz."""
        with self._lock:
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._chunks)[:, 0].astype(np.float32) / 32768.0


class STT:
    def __init__(self):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
        log.info("Whisper %s loaded", config.WHISPER_MODEL)

    def transcribe(self, audio):
        if len(audio) < RATE * 0.4:
            return ""
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
