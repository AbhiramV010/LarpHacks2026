# QUACKSWORTH

A rubber duck that listens while you think out loud, rewrites your ramble as a clear prompt for Claude, says a line, and types the prompt into the window that has focus. Built for LarpHacks 2026 by Abhiram Vadali and Mridul Goel.

If the request is reckless, such as pushing straight to main, deleting failing tests, or committing an API key, the duck refuses. It turns to face you, lights its laser eye, shakes its sword, and stays angry until you reset it.

The cost dial (LOW, MEDIUM, HIGH) is fake on purpose. It changes the price on screen and nothing else. The roast dial (POLITE, SNARKY, UNHINGED) is real: it sets the duck's tone and how fast its patience runs out.

## Parts

- `laptop/`: speech recognition (faster-whisper), prompt rewriting and blunder scoring (Gemma through Ollama), speech (ElevenLabs, or the Windows voice offline), typing (pynput), and the overlay.
- `unoq_app/`: the duck's body on an Arduino Uno Q. RGB light, laser eye, OLED, a stepper that turns the duck, a button, and the dial.
- `laptop/overlay.html`: shows what you said next to what the duck typed.

## Run it

```powershell
pip install -r laptop\requirements.txt
python laptop\overlay_server.py
python laptop\duck_main.py
```

Open `laptop\overlay.html` in Chrome. Set `ELEVENLABS_API_KEY` first if you want the ElevenLabs voice.

Keys: F8 resets the duck, F10 stops speech and typing. The button on the Uno Q does the same as F8.

The laptop works without the Uno Q. The health dot on the overlay shows when the board is missing.

## Tests

- `laptop\test_blunders.py`: checks that calm requests score low and reckless ones score high.
- `laptop\test_link.py`: sends every command to the board and prints what comes back.
- `laptop\fake_events.py`: plays a scripted session on the overlay with no hardware.
- `unoq_app\test_sketch.ino`: checks each part of the board from the Serial Monitor.

## Uno Q setup

Open `unoq_app` in Arduino App Lab and run it. The sketch needs one patch to the Adafruit SSD1306 library so it compiles on the Uno Q's Zephyr core. In `Adafruit_SSD1306.h`, add `&& !defined(ARDUINO_ARCH_ZEPHYR)` to the `#elif` that ends with `!defined(ARDUINO_ARCH_RP2040)`.
