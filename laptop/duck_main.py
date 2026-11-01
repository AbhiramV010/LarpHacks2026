"""The duck's state machine. Hotkeys: F7 push-to-talk, F8 reset, F10 kill switch."""
import asyncio
import json
import logging
import queue
import threading
import time

from pynput import keyboard

import config
import typer
from brain import Brain
from link import Link
from speech import STT, TTS, Recorder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("duck")

TIERS = [  # (max_pot, tier, price, roast, single_trigger, total_trigger)
    (340, "LOW", "FREE", "POLITE", 9, 15),
    (681, "MEDIUM", "$9.99/mo", "SNARKY", 8, 12),
    (1023, "HIGH", "PREMIUM $49.99/mo", "UNHINGED", 6, 8),
]
BURN = {"LOW": 0.0, "MEDIUM": 0.37, "HIGH": 4.20}


def tier_for(pot):
    for row in TIERS:
        if pot <= row[0]:
            return row
    return TIERS[-1]


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
        self.rec = Recorder()
        self.state = "idle"
        self.pot = 0
        self.locked = tier_for(0)
        self.total_blunder = 0
        self.burn = 0.0
        self.history = []
        self.work = queue.Queue()      # requests from hotkey/UDP threads to the main loop
        self.busy = threading.Lock()
        self.stt = STT()
        self.brain.warm()
        self.reset()

    # ---- state helpers ----
    def set_state(self, name):
        self.state = name
        self.link.send(f"STATE {name}")
        self.overlay.send("state", state=name)
        log.info("STATE %s", name.upper())

    def send_dial(self):
        _, tier, price, roast, _, _ = tier_for(self.pot)
        self.overlay.send("dial", raw=self.pot, tier=tier, price=price, roast=roast,
                          locked_tier=self.locked[1], locked_roast=self.locked[3])

    def send_patience(self):
        mx = self.locked[5]
        self.overlay.send("patience", value=max(0, mx - self.total_blunder), max=mx)

    def send_health(self):
        self.overlay.send("health", unoq=self.link.up, ollama=self.brain.ok, mic=self.rec.ok)

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

    # ---- the pipeline ----
    def on_press(self):
        if self.state != "idle":
            return
        self.set_state("listening")
        self.rec.start()
        self.t0 = time.time()

    def on_release(self):
        if self.state != "listening":
            return
        audio = self.rec.stop()
        if time.time() - self.t0 < 0.4 or len(audio) == 0:
            self.set_state("idle")
            return
        self.set_state("translating")
        text = self.stt.transcribe(audio)
        log.info("Heard: %s", text)
        if not text:
            self.set_state("idle")
            return
        self.overlay.send("heard", text=text)
        _, tier, price, roast, single, total = self.locked
        r = self.brain.ask(text, roast, self.history)
        self.send_health()
        log.info("Brain: %s", r)
        self.history = (self.history + [{"transcript": text, "result": r}])[-2:]
        self.total_blunder += r["blunder"]
        self.burn += BURN[tier]
        self.overlay.send("burn", amount=round(self.burn, 2))
        self.send_patience()
        self.overlay.send("prompt", text=r["prompt"])

        if r["blunder"] >= single or self.total_blunder >= total:
            reason = r["reason"] or "being reckless"
            self.set_state("angry")
            self.link.send("ANGER")
            self.overlay.send("angry", reason=reason)
            line = self.brain.angry_line(reason, roast, tier, price)
            self.overlay.send("say", text=line)
            self.tts.say(line)
            return  # stays angry until F8/RESET

        self.link.send("PAN 90")
        self.set_state("talking")
        self.overlay.send("say", text=r["say"])
        self.tts.say(r["say"])
        if self.state != "talking":
            return  # killed by F10
        self.link.send("PAN 0")
        self.set_state("typing")
        done = typer.type_prompt(r["prompt"], on_typing=lambda on: self.link.send(f"TYPING {int(on)}"))
        if done:
            self.set_state("waiting")
            time.sleep(1.0)
        if self.state in ("typing", "waiting"):
            self.set_state("idle")

    def kill(self):
        typer.stop_flag.set()
        TTS.stop()
        if self.state == "listening":
            self.rec.stop()
        self.set_state("idle")

    # ---- input sources ----
    def on_event(self, ev):
        if ev == "BTN DOWN":
            self.work.put("press")
        elif ev == "BTN UP":
            self.work.put("release")
        elif ev.startswith("POT "):
            try:
                self.pot = int(ev[4:])
                self.send_dial()
            except ValueError:
                pass
        elif ev == "RESET":
            self.work.put("reset")

    def hotkeys(self):
        def on_press(k):
            if k == keyboard.Key.f7:
                self.work.put("press")
            elif k == keyboard.Key.f8:
                self.work.put("reset")
            elif k == keyboard.Key.f10:
                self.kill()

        def on_release(k):
            if k == keyboard.Key.f7:
                self.work.put("release")
        keyboard.Listener(on_press=on_press, on_release=on_release).start()

    def run(self):
        self.hotkeys()
        log.info("%s ready. F7 = talk, F8 = reset, F10 = kill.", config.DUCK_NAME)
        last_health = 0
        while True:
            try:
                self.on_event(self.link.events.get_nowait())
            except queue.Empty:
                pass
            try:
                job = self.work.get(timeout=0.05)
            except queue.Empty:
                job = None
            if job == "press":
                self.on_press()
            elif job == "release":
                threading.Thread(target=self._guarded, args=(self.on_release,), daemon=True).start()
            elif job == "reset":
                self.reset()
            if time.time() - last_health > 2:
                self.send_health()
                last_health = time.time()

    def _guarded(self, fn):
        if self.busy.acquire(blocking=False):
            try:
                fn()
            except Exception:
                log.exception("pipeline error")
                self.set_state("idle")
            finally:
                self.busy.release()


if __name__ == "__main__":
    Duck().run()
