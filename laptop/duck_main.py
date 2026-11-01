"""The duck's state machine. Always listening. Hotkeys: F8 reset, F10 kill switch. Button D12 = reset."""
import asyncio
import difflib
import json
import logging
import queue
import subprocess
import threading
import time

from pynput import keyboard

import config
import notepad
import typer
from brain import Brain
from link import Link
from speech import STT, TTS, Listener

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("duck")

TIERS = [  # (max_pot, tier, price, roast, single_trigger, total_trigger)
    (340, "LOW", "FREE", "POLITE", 9, 15),
    (681, "MEDIUM", "$9.99/mo", "SNARKY", 8, 12),
    (1023, "HIGH", "PREMIUM $49.99/mo", "UNHINGED", 6, 8),
]
BURN = {"LOW": 0.0, "MEDIUM": 0.37, "HIGH": 4.20}
SELF_HEAR_GUARD_S = 0.5


def tier_for(pot):
    for row in TIERS:
        if pot <= row[0]:
            return row
    return TIERS[-1]


def strip_wake_word(text, wake):
    """Return the text after the wake word, or None if it isn't there (fuzzy)."""
    words = text.split()
    if len(words) < 2:
        return None
    head = " ".join(w.lower().strip(".,!?") for w in words[:2])
    if head in ("a duck", "hey duc", "a duc") or difflib.SequenceMatcher(None, head, wake).ratio() >= 0.7:
        return " ".join(words[2:]).strip() or None
    return None


class Overlay:
    """Fire-and-forget websocket client; silently drops events if the server is down."""
    def __init__(self):
        self.q = queue.Queue()
        threading.Thread(target=lambda: asyncio.run(self._run()), daemon=True).start()

    def send(self, type_, **fields):
        self.q.put(json.dumps({"type": type_, **fields}))

    async def _run(self):
        import websockets
        warned = False
        while True:
            try:
                async with websockets.connect(config.OVERLAY_WS) as ws:
                    log.info("Overlay connected")
                    warned = False
                    while True:
                        try:
                            msg = self.q.get_nowait()
                        except queue.Empty:
                            await asyncio.sleep(0.05)
                            continue
                        await ws.send(msg)
            except Exception as e:
                if not warned:
                    log.warning("Overlay server not reachable (%s); continuing without it", e)
                    warned = True
                await asyncio.sleep(2)


class Duck:
    def __init__(self):
        self.overlay = Overlay()
        self.link = Link()
        self.brain = Brain()
        self.tts = TTS()
        self.state = "idle"
        self.pot = 0
        self.locked = tier_for(0)
        self.total_blunder = 0
        self.burn = 0.0
        self.history = []
        self.speaking = False        # duck audio is playing
        self.mute_until = 0.0        # self-hearing guard end time
        self.work = queue.Queue()    # reset requests from F8 / button, drained by the main loop
        self.space_down = False
        self.busy = threading.Lock()
        self.stt = STT()
        self.listener = Listener(self.muted, self.on_level)
        self.brain.warm()
        self.reset()

    # ---- gating ----
    def muted(self):
        return (self.speaking or self.state in ("translating", "talking", "typing")
                or time.time() < self.mute_until)

    def _end_audio(self):
        self.mute_until = time.time() + SELF_HEAR_GUARD_S

    # ---- state helpers ----
    def set_state(self, name):
        self.state = name
        self.link.send(f"STATE {name}")
        self.overlay.send("state", state=name)
        log.info("STATE %s", name.upper())

    def on_level(self, rms, threshold):
        self.overlay.send("mic", rms=round(rms, 4), threshold=round(threshold, 4))

    def send_dial(self):
        _, tier, price, roast, _, _ = tier_for(self.pot)
        self.overlay.send("dial", raw=self.pot, tier=tier, price=price, roast=roast,
                          locked_tier=self.locked[1], locked_roast=self.locked[3])

    def send_patience(self):
        mx = self.locked[5]
        self.overlay.send("patience", value=max(0, mx - self.total_blunder), max=mx)

    def send_health(self):
        self.overlay.send("health", unoq=self.link.up, ollama=self.brain.ok, mic=self.listener.ok)

    def reset(self):
        typer.stop_flag.set()
        TTS.stop()
        self.history = []
        self.total_blunder = 0
        self.locked = tier_for(self.pot)
        self.link.send("RESET")
        self.overlay.send("reset")
        self.overlay.send("name", name=config.DUCK_NAME)
        self.set_state("idle")
        self.send_dial()
        self.send_patience()
        self.overlay.send("burn", amount=round(self.burn, 2))
        self.listener.recalibrate()
        self._end_audio()

    def kill(self):
        typer.stop_flag.set()
        TTS.stop()
        self.set_state("idle")
        self._end_audio()

    # ---- pipeline ----
    def process(self, audio):
        """Runs in a worker thread. The transcript goes straight to Gemma; the code is typed into Notepad."""
        self.set_state("translating")
        text = self.stt.transcribe(audio)
        if config.WAKE_WORD:
            text = strip_wake_word(text, config.WAKE_WORD) or ""
        log.info("Heard: %s", text)
        if not text:
            self.set_state("idle")
            return
        self.overlay.send("heard", text=text)
        existing = notepad.read_current()  # what's in Notepad now, so Gemma can edit it
        code = self.brain.code(text, existing)
        self.overlay.send("prompt", text=code[:2000])
        notepad.open_and_focus()
        time.sleep(1.5)  # let Notepad take focus
        notepad.select_all()  # the typed file replaces whatever is there
        self.set_state("typing")
        done = typer.type_prompt(code, on_typing=lambda on: self.link.send(f"TYPING {int(on)}"), code=True)
        self._end_audio()
        if done:
            self.set_state("waiting")
            time.sleep(1.0)
        if self.state in ("typing", "waiting"):
            self.set_state("idle")

    def speak(self, line):
        self.speaking = True
        try:
            self.tts.say(line)
        finally:
            self.speaking = False
            self._end_audio()

    def _guarded(self, audio):
        if self.busy.acquire(blocking=False):
            try:
                self.process(audio)
            except Exception:
                log.exception("pipeline error")
                self.set_state("idle")
            finally:
                self.busy.release()

    # ---- input sources ----
    def on_link_event(self, ev):
        if ev == "BTN DOWN":
            self.work.put("reset")
        elif ev.startswith("POT "):
            try:
                self.pot = int(ev[4:])
                self.send_dial()
            except ValueError:
                pass

    def hotkeys(self):
        def on_press(k):
            if k == keyboard.Key.f8:
                self.work.put("reset")
            elif k == keyboard.Key.f10:
                self.kill()
            elif k == keyboard.Key.space and not self.space_down and self.state == "idle" and not self.muted():
                self.space_down = True
                self.listener.ptt_press()
                self.set_state("listening")

        def on_release(k):
            if k == keyboard.Key.space and self.space_down:
                self.space_down = False
                self.listener.ptt_release()
        keyboard.Listener(on_press=on_press, on_release=on_release).start()

    def run(self):
        self.hotkeys()
        self.listener.start()
        log.info("%s ready. Just talk. F8 = reset, F10 = kill.", config.DUCK_NAME)
        last_health = 0
        while True:
            try:
                self.on_link_event(self.link.events.get_nowait())
            except queue.Empty:
                pass
            try:
                job = self.work.get_nowait()
            except queue.Empty:
                job = None
            if job == "reset":
                self.reset()
            audio = None
            try:
                kind, audio = self.listener.events.get(timeout=0.05)
            except queue.Empty:
                kind = None
            if kind == "start" and self.state == "idle":
                self.set_state("listening")
            elif kind == "cancel" and self.state == "listening":
                self.set_state("idle")
            elif kind == "audio" and self.state == "listening":
                threading.Thread(target=self._guarded, args=(audio,), daemon=True).start()
            if time.time() - last_health > 2:
                self.send_health()
                last_health = time.time()


if __name__ == "__main__":
    Duck().run()
