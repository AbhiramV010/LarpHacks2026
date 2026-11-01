# QUACKSWORTH — the rubber duck that vibe-codes for you (and refuses when you're reckless)

LarpHacks 2026 · Abhiram Vadali & Mridul Goel

## What it does

Hold the duck's button and ramble about your coding problem. The laptop transcribes it, a local
Gemma model rewrites the ramble into a clean, specific prompt for Claude, the duck says a line out
loud, then types the prompt into whatever Claude window has focus.

Every request also gets a **blunder score** (0–10). Ask for something reckless — push straight to
main, delete the tests, commit an API key, `rm -rf` — and the duck refuses to type it. It turns to
face you, lights its laser eyes, shakes the sword glued to its body, and tells you off. It stays
angry until you press reset.

One potentiometer sets two things:

- **Cost tier (fake, on purpose):** LOW / FREE, MEDIUM / $9.99, HIGH / PREMIUM $49.99. It changes
  nothing. Every tier runs the same model. The angry line mocks you for paying for it.
- **Roast intensity (real):** POLITE / SNARKY / UNHINGED. Changes the duck's tone and how fast it
  loses patience (patience bar on the overlay; each request's blunder score eats into it).

A second, smaller Gemma runs on the Uno Q itself. It writes OLED one-liners while the duck waits
(`quack. ship it.`) and is the fallback brain if the laptop's Ollama dies.

## How it works

```
LAPTOP (Windows)                                    ARDUINO UNO Q
duck_main.py   state machine, hotkeys F7/F8/F10     Linux (python/main.py)
  speech.py    mic -> faster-whisper (STT)            UDP :5005  <- commands from laptop
               ElevenLabs / Windows voice (TTS)       Bridge.call("cmd") -> MCU
  brain.py     Ollama gemma3:4b, JSON out             Bridge.provide("event") <- MCU
  typer.py     pynput types into Claude               UDP -> laptop :5006 (BTN, POT, PONG)
  link.py      UDP <-> unoq.local                     quips from local gemma3:1b -> OLED
  overlay_server.py  WebSocket :8765                MCU (sketch/sketch.ino, Zephyr)
overlay.html   projector page                         RGB LED, laser eyes, OLED, pan stepper
                                                      (also swings the sword), button, pot
```

Flow: `BTN DOWN` → LISTENING → `BTN UP` → TRANSLATING (whisper + gemma) → calm: TALKING (duck
faces you) → TYPING (duck faces laptop) → WAITING → IDLE. Reckless: ANGRY until RESET.
Python decides when the duck flips (single request ≥ trigger, or running total ≥ trigger, both set
by the locked roast level) — never the model.

Protocol is plain-text UDP, one command per packet: `STATE`, `OLED`, `PAN`, `EYES`, `TYPING`,
`ANGER`, `RESET`, `PING` → board; `BTN DOWN/UP`, `POT n`, `PONG` → laptop.

## Hardware

- Arduino Uno Q (Dragonwing QRB2210 Linux side + STM32U585 MCU, Arduino RouterBridge between them)
- 28BYJ-48 stepper + ULN2003 (D2, D4, D7, D8) pans the duck and the craft-stick sword, external 5 V
- Common-cathode RGB LED (D6 R, D5 G, D3 B), two red "laser eye" LEDs (D10, D11)
- SSD1306 128x64 OLED on I2C (0x3C)
- Push button (D12, pull-up), potentiometer (A2)
- Lenovo laptop, USB webcam mic, laptop speaker, phone hotspot linking the two

Duck must face the laptop at power-on (angle 0). 90° faces the user. Stepper never runs above
15 RPM or it skips steps.

## Run

Laptop (PowerShell, everything local — Ollama with `gemma3:4b` pulled):

```powershell
pip install -r laptop\requirements.txt
$env:ELEVENLABS_API_KEY = "..."        # optional; without it the Windows voice is used (offline)
python laptop\overlay_server.py        # terminal 1
python laptop\duck_main.py             # terminal 2 (loads whisper, warms gemma)
# open laptop\overlay.html in Chrome, F11 full screen (?name=QUACKSWORTH)
```

F7 = push-to-talk (same as the duck's button), F8 = reset, F10 = kill switch (stops speech and
typing mid-prompt). Click into Claude's input box before releasing the button.

One-time Windows setup (elevated PowerShell), then set the hotspot network to Private:

```powershell
New-NetFirewallRule -DisplayName "Duck UDP 5006" -Direction Inbound -Protocol UDP -LocalPort 5006 -Action Allow -Profile Private
```

If `unoq.local` doesn't resolve, set `UNOQ_HOST` to the board's IP in `laptop/config.py`.
Without the board the laptop still runs voice, typing and overlay; the UNO Q health dot goes red.

Uno Q: open `unoq_app/` in Arduino App Lab and run it (`app.yaml` requests host networking so
UDP 5005/5006 reach the container). The sketch needs the Adafruit_SSD1306 Zephyr patch: in
`Adafruit_SSD1306.h`, the `#elif` ending in `!defined(ARDUINO_ARCH_RP2040)` must also have
`&& !defined(ARDUINO_ARCH_ZEPHYR)`. The on-device model is installed by the
`unoq-model-installer` agent (`.claude/agents/`); put the container-reachable Ollama address in
`unoq_app/python/main.py`.

Tests: `python laptop\test_blunders.py` (calm ≤ 4, reckless ≥ 7 — passes 10/10),
`python laptop\test_link.py` (board round-trip), `python laptop\fake_events.py` (overlay demo
with no hardware).

## Yes, the cost tier is fake

That's the joke. The dial shows LOW / MEDIUM / HIGH with prices and a gold glow on PREMIUM; the
burn meter ticks up $4.20 a request. None of it changes the model. Only the roast level is real.
