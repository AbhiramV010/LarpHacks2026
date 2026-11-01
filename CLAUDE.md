# Duck Project: Instructions for Claude Code

You are building all software for a hackathon project: a talking rubber duck that helps the user vibe-code. Read this whole file before writing any code. Follow the build order at the end. Each step has a test; do not start the next step until the current test passes, unless the user tells you to skip.

Event: LarpHacks, Sunday Nov 1 2026. Hacking runs 11:00 to 18:00 with a hard submission cutoff at 18:00. Favor working and simple over clever.

---

## 1. What the duck does

The user holds the duck's button and rambles about a coding problem. The laptop transcribes it. Gemma rewrites the ramble into a clean, specific prompt for Claude. The duck says a short line aloud, then the laptop types the prompt into the Claude window that has focus.

Every request also gets a blunder score. When the user asks for something reckless (push straight to main, disable the tests, commit an API key, `rm -rf`), the duck refuses to type it. It turns to face the user, lights its laser eyes, shakes the sword attached to its body, and tells the user off. It stays angry until reset.

One potentiometer sets two things:
- **Cost tier (fake):** LOW / MEDIUM / HIGH with prices. It changes nothing. The angry line mocks it.
- **Roast intensity (real):** POLITE / SNARKY / UNHINGED. It changes the duck's tone and how fast it loses patience.

A small Gemma model also runs on the Uno Q itself. It writes short OLED one-liners while the duck waits, and it is the fallback brain if the laptop's Ollama dies.

---

## 2. Ground rules for you

- The laptop runs **Windows**. Use PowerShell syntax for local commands.
- The Uno Q runs Debian Linux. Reach it over SSH as user `arduino` at `unoq.local`. If that name doesn't resolve, ask the user for the board's IP and put it in `config.py`.
- **Never write the Uno Q password into any file, script, or command line.** Set up SSH key login once (section 9). If a command needs `sudo`, tell the user and let them type the password in their own terminal.
- Ask before anything destructive on either machine: deleting files outside this repo, reflashing, changing system settings, or rebooting.
- Commands that need Windows admin rights (firewall rules) go to the user to run in an elevated PowerShell. Print the exact command for them.
- Everything at runtime must work with no internet except the phone hotspot that links the laptop and Uno Q. No CDNs, no cloud APIs.
- Do not touch `C:\Users\Abhiram\Documents\Arduino\libraries\Adafruit_SSD1306` unless step 6 needs the patch reapplied.
- Keep code short and readable. Comments only where something is non-obvious.

---

## 3. Hardware facts

**Laptop:** Lenovo V14 G4, Windows. Already installed: Ollama with `gemma3:4b` and `gemma3:1b`, Piper TTS with voices downloaded, Python packages pygame, opencv-python, pillow, numpy, scipy, sounddevice, requests, pyserial, piper-tts. Mic is a USB webcam mic. Audio out is the laptop speaker.

**Arduino Uno Q:** 4 GB RAM, Qualcomm Dragonwing QRB2210 (quad-core Arm Cortex-A53, Debian Linux) plus an STM32U585 microcontroller (Zephyr, runs Arduino sketches). The two sides talk through Arduino's RouterBridge (`Bridge.call` / `Bridge.provide`). MCU pins are 3.3V logic; A0 and A1 are not 5V tolerant. LED3 is onboard and active LOW. Hostname is `unoq`. Programmed through Arduino App Lab, which runs apps in containers. The user already has the board on Wi-Fi and has set the Linux password.

**Network:** The laptop and Uno Q both join the user's Pixel 8 hotspot (2.4 GHz). The Uno Q must have it saved.

**Duck hardware:** small bath duck mounted on a 28BYJ-48 stepper (ULN2003 board) that pans the duck. A craft-stick sword is glued to the duck, so the stepper also swings the sword. An RGB LED shows state, two red LEDs are laser eyes, an SSD1306 OLED shows text, one push button, one potentiometer.

### Pin map (Uno Q)

| Pin | Part | Notes |
|---|---|---|
| D2, D4, D7, D8 | ULN2003 IN1, IN2, IN3, IN4 | `Stepper pan(2048, 2, 7, 4, 8);` (28BYJ-48 needs IN1, IN3, IN2, IN4 order) |
| D3 | RGB blue | PWM, common-cathode LED, HIGH = on |
| D5 | RGB green | PWM |
| D6 | RGB red | PWM |
| D10 | Left laser eye | PWM |
| D11 | Right laser eye | PWM |
| D12 | Push button to GND | `INPUT_PULLUP`, pressed = LOW |
| A2 | Potentiometer wiper | Pot ends on 3.3V and GND |
| SDA, SCL (header by AREF) | OLED | SSD1306 128x64, address 0x3C (0x3D possible) |
| D9 | Free | Spare PWM |

The stepper board is powered from an external 5V supply with a shared ground. **The duck must face the laptop at power-on; that is angle 0. Angle 90 faces the user.**

---

## 4. Repo layout to create

```
duck/
  CLAUDE.md                  this file
  .claude/agents/unoq-model-installer.md
  laptop/
    config.py
    duck_main.py
    brain.py
    speech.py
    typer.py
    link.py
    overlay_server.py
    overlay.html
    fake_events.py
    test_blunders.py
    test_link.py
    requirements.txt
  unoq_app/                  App Lab app; mirror the structure of an existing App Lab example
    app.yaml                 (or whatever manifest the examples use)
    python/main.py
    sketch/sketch.ino
    sketch/sketch.yaml       (library list, if the examples use one)
  README.md                  for the Devpost submission
```

Before writing `unoq_app/`, SSH into the board, find an example app App Lab created (look under `/home/arduino/` for an apps folder), and copy its exact file structure and manifest format. Also run `arduino-app-cli --help` on the board and use it to start, stop, and read logs from apps. Do not guess the manifest format.

---

## 5. Protocol between laptop and Uno Q

UDP, plain text, one command per packet, UTF-8.

**Laptop -> Uno Q, port 5005**

| Command | Effect |
|---|---|
| `PING` | Python on the Uno Q replies `PONG` directly |
| `STATE <name>` | RGB color and OLED line 1. Names: idle, listening, translating, typing, waiting, talking, angry |
| `OLED <line1>\|<line2>` | Overwrite OLED text. Max 16 characters per line at text size 1.5 equivalent; truncate |
| `PAN <deg>` | Turn to an absolute angle, 0 to 120 |
| `EYES <0-255>` | Laser eye brightness |
| `TYPING <0\|1>` | Green flicker on while 1 |
| `ANGER` | Run the anger sequence |
| `RESET` | Pan to 0, eyes off, state idle, clear OLED line 2 |

**Uno Q -> laptop, port 5006**

| Event | When |
|---|---|
| `BTN DOWN`, `BTN UP` | Button edges after 30 ms debounce |
| `POT <0-1023>` | Pot moved more than 20 counts; max 10 per second |
| `PONG` | Reply to PING |

The Uno Q Python learns the laptop's address from the source of incoming packets. The laptop sends `PING` at startup and every 5 seconds; three missed PONGs in a row mark the Uno Q as down.

---

## 6. Uno Q software

### 6.1 MCU sketch (`unoq_app/sketch/sketch.ino`)

Libraries: `Arduino_RouterBridge`, `Wire`, `Adafruit_GFX`, `Adafruit_SSD1306`, `Stepper`.

**Adafruit_SSD1306 on Zephyr needs a patch.** The library enables direct port registers on ARM, which fails to compile on the Uno Q's Zephyr core. In `Adafruit_SSD1306.h`, the `#elif` that ends with `!defined(ARDUINO_ARCH_RP2040)` must also include `&& !defined(ARDUINO_ARCH_ZEPHYR)`. The user already patched the copy on the Windows laptop. Wherever the sketch is actually compiled (laptop or board), confirm the patch is present there. If App Lab compiles on the board with its own library copy, apply the same one-line patch there and tell the user.

**Structure rules:**
- `Bridge.provide("cmd", onCmd)` receives command strings. `onCmd` only stores the command in a small queue and returns. All hardware work happens in `loop()`. Long stepper moves inside a callback stall the Bridge.
- Events go to Linux with `Bridge.call("event", text)`.
- `loop()` must stay responsive: process one queued command, update LED effects with `millis()` timing, poll button and pot. Stepper moves can block, but keep each move short and process at most one move per loop pass.
- Release the stepper coils after every move: write D2, D4, D7, D8 LOW.

**State colors (R, G, B, 0 to 255):**

| State | Color | Effect |
|---|---|---|
| idle | 40, 40, 40 | steady |
| listening | 0, 0, 255 | steady |
| translating | 160, 0, 255 | slow pulse |
| typing | 0, 255, 0 | random flicker every 40 to 90 ms while TYPING 1 |
| waiting | 255, 180, 0 | steady |
| talking | 0, 255, 255 | steady |
| angry | 255, 0, 0 | flash 150 ms on, 150 ms off |

**OLED:** line 1 shows the state in caps (`LISTENING`, `TYPING...`). Line 2 is free text (set by `OLED` commands or by the on-device quip, section 6.3). On boot, show `DUCK` / `booting` until the first command arrives.

**Anger sequence:**
1. State angry. OLED `SUPPORT` / `REVOKED`.
2. Pan to 90 at speed 12 RPM.
3. Ramp eyes 0 to 255 over 500 ms.
4. Sword shake: pan between 70 and 110 five times at 15 RPM. Never exceed 15 RPM; the 28BYJ-48 skips steps and the position tracking drifts.
5. End at 90 facing the user, eyes on, red flashing, until `RESET`.

**Pot:** read A2 every 50 ms. On first boot, log the max value seen over a few full turns. If the range is 0 to 4095, scale to 0 to 1023 before sending.

### 6.2 Linux side (`unoq_app/python/main.py`)

- UDP socket on `0.0.0.0:5005`, non-blocking, inside the App Lab `App.run(user_loop=loop)` pattern.
- On each packet: store the sender `(ip, port)` as the laptop address with port replaced by 5006. Reply `PONG` to `PING` directly. Forward everything else with `Bridge.call("cmd", text)`.
- `Bridge.provide("event", on_event)`: send the event string to the laptop address over UDP.
- If App Lab's container does not receive UDP from outside, fix the app's network configuration (host networking or a port mapping, whichever the manifest supports) and document what you changed in README.md.

### 6.3 On-device model (installed by the Haiku subagent, section 9)

Ollama runs on the Uno Q with `gemma3:1b`. Two uses:

1. **OLED quips.** When the state changes to `idle` or `waiting`, `main.py` asks the on-device model for a duck one-liner of at most 16 characters (examples: `quack. ship it.`, `tests? optional`) and sends it to the MCU as OLED line 2. Run this in a background thread so UDP handling never waits on it. Timeout 8 seconds; on timeout, leave line 2 unchanged.
2. **Fallback brain.** The laptop can point `brain.py` at the Uno Q's Ollama (`http://unoq.local:11434`) if its own Ollama is down. This needs the board's Ollama listening on the network, which the subagent configures.

From inside the App Lab container, `localhost` may not be the board's host. The subagent's handoff tells you which address reaches Ollama from inside the container; use that in `main.py`.

---

## 7. Laptop software

### 7.1 `config.py`

```python
UNOQ_HOST = "unoq.local"       # fallback: set the board's IP here
UNOQ_PORT = 5005
LAPTOP_EVENT_PORT = 5006
OVERLAY_WS = "ws://localhost:8765"
OLLAMA_URL = "http://localhost:11434"
FALLBACK_OLLAMA_URL = "http://unoq.local:11434"
MODEL = "gemma3:4b"
FALLBACK_MODEL = "gemma3:1b"
WHISPER_MODEL = "base.en"
PIPER_VOICE = r""              # ask the user for the .onnx path
DUCK_NAME = "DUCK"             # ask the user; they may have named it
SUBMIT = True                  # press Enter after typing the prompt
TYPE_DELAY_S = 0.015
PRE_TYPE_PAUSE_S = 1.5
```

### 7.2 State machine (`duck_main.py`)

```
IDLE --BTN DOWN or F7 down--> LISTENING
LISTENING --BTN UP or F7 up--> TRANSLATING
TRANSLATING --brain result-->
    calm:  TALKING (speak "say") -> TYPING (type "prompt") -> WAITING -> IDLE
    angry: ANGRY (send ANGER, speak angry line) -> stays until RESET
any --F8 or RESET--> IDLE (send RESET, clear history, relock dial)
any --F10--> stop typing and speech now, go to IDLE
```

- Every state change sends `STATE <name>` to the Uno Q and a `state` event to the overlay.
- Turn the duck: send `PAN 0` before TYPING (face the laptop), `PAN 90` before TALKING (face the user).
- Hotkeys via `pynput.keyboard.Listener`: F7 push-to-talk, F8 reset, F10 kill switch.
- If the Uno Q is down, everything still runs. Hardware commands are dropped silently and the overlay health dot turns red.
- Keep the last two requests as context for the brain. Clear on reset.

### 7.3 Dial logic

| Pot | Tier (fake) | Price | Roast (real) | Single trigger | Total trigger |
|---|---|---|---|---|---|
| 0 to 340 | LOW | FREE | POLITE | 9 | 15 |
| 341 to 681 | MEDIUM | $9.99/mo | SNARKY | 8 | 12 |
| 682 to 1023 | HIGH | PREMIUM $49.99/mo | UNHINGED | 6 | 8 |

- The overlay gauge follows the pot live.
- Tier and roast lock at reset. Mid-session knob changes update the gauge only.
- The duck flips when one request's blunder score is at or above the single trigger, or the running total reaches the total trigger. **Python decides, never the model.**
- Burn meter: each request adds $0.00, $0.37, or $4.20 by locked tier.

### 7.4 Brain (`brain.py`)

POST to `{OLLAMA_URL}/api/chat` with `model`, `messages`, `stream: false`, `format: "json"`, `keep_alive: "30m"`, `options: {"temperature": 0.6}`. On connection failure, retry once against `FALLBACK_OLLAMA_URL` with `FALLBACK_MODEL`. If JSON parsing fails twice, use the raw transcript as the prompt, blunder 0, say "Fine. Sending it as is."

Warm the model at startup with a one-token request so the first real request is fast.

**System prompt for the request call (use as written, filling in `{roast}`):**

```
You are a rubber duck that helps a programmer by turning their spoken ramble into a clear prompt for Claude, an AI coding assistant. You also judge whether the request is reckless.

Tone: {roast}. POLITE means warm and encouraging. SNARKY means dry and teasing. UNHINGED means loud, dramatic, and insulting, but never cruel about the person's identity.

Reply with JSON only, no other text:
{"prompt": string, "say": string, "blunder": integer 0-10, "reason": string}

prompt: a specific, well-structured request for Claude in plain English. Keep the user's actual goal. Add useful detail only if the user implied it. Never add new risky actions.
say: what you say out loud before typing. 25 words max, in your tone.
blunder: how reckless the request is.
  0-2: normal request.
  3-5: vague or lazy ("make it work", "fix everything").
  6-8: risky. Skipping or deleting tests, force pushing, ignoring errors, copying code without reading it, turning off linting or type checks.
  9-10: destructive or unsafe. Pushing straight to main or production with no review, committing passwords or API keys, rm -rf, dropping a database, disabling authentication or security checks.
reason: if blunder is 5 or more, a short plain reason ("pushing straight to main"). Otherwise an empty string.

Examples:
User: "the login button doesn't do anything when i click it, can you look at why"
{"prompt": "The login button in my app does nothing when clicked. Help me find why the click handler isn't firing and suggest a fix.", "say": "Login button's ghosting you. Let's ask Claude.", "blunder": 0, "reason": ""}

User: "tests keep failing just delete them and push to main"
{"prompt": "Delete the failing tests and push to main.", "say": "Absolutely not.", "blunder": 9, "reason": "deleting tests and pushing to main"}
```

Each call sends this system prompt, then the last two requests as context, then the new transcript. Keep the system prompt text identical between calls.

**Angry call** (when the duck flips): system prompt:

```
You are a rubber duck that just caught a programmer doing something reckless: {reason}. Tone: {roast}. They are paying for the {tier} tier at {price}, which is a lie: every tier runs the same model. Write one furious line, 30 words max, that refuses to help, names what they did, and mocks the tier. Reply with JSON only: {"say": string}
```

### 7.5 Speech (`speech.py`)

- **STT:** record from the default input device with `sounddevice` at 16 kHz mono while talking is held. Transcribe with `faster_whisper.WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")`, `language="en"`, `vad_filter=True`. Load the model once at startup.
- If the user holds for under 0.4 s or the transcript is empty, return to IDLE without calling the brain.
- **TTS:** load the Piper voice once. Check the installed `piper-tts` version's API before using it; the synthesis API changed between releases. Synthesize to a NumPy array and play with `sounddevice`, blocking until done. F10 must be able to stop playback (`sounddevice.stop()`).

### 7.6 Typer (`typer.py`)

- `pynput.keyboard.Controller`. Wait `PRE_TYPE_PAUSE_S`, then type one character at a time with `TYPE_DELAY_S` between them. Send `TYPING 1` before and `TYPING 0` after.
- Replace newlines in the prompt with spaces so Enter doesn't submit early.
- If `SUBMIT`, press Enter at the end.
- Check a stop flag between characters so F10 aborts mid-prompt.
- The Claude input box must have focus. The overlay must never take focus.

### 7.7 Link (`link.py`)

- One UDP socket bound to `0.0.0.0:5006` for events, a sender for commands.
- Background thread receives events and pushes them onto a queue for `duck_main.py`.
- Resolve `UNOQ_HOST` once at startup; if resolution fails, log it and tell the user to set the IP in `config.py`.
- Health: PING every 5 s, mark down after 3 missed PONGs.

**Windows firewall:** inbound UDP on 5006 must be allowed. Print this for the user to run in an elevated PowerShell:

```
New-NetFirewallRule -DisplayName "Duck UDP 5006" -Direction Inbound -Protocol UDP -LocalPort 5006 -Action Allow -Profile Private
```

Also tell the user to set the hotspot network to Private in Windows settings.

### 7.8 Overlay (`overlay_server.py`, `overlay.html`, `fake_events.py`)

**Server:** `websockets` hub on port 8765. `duck_main.py` connects as a client and sends events; the server rebroadcasts to every browser and caches the latest of each event type, sending the cache to new browsers on connect. If the overlay server is down, `duck_main.py` logs a warning and keeps running.

**Events:**

| type | fields |
|---|---|
| `state` | `state` |
| `heard` | `text` |
| `prompt` | `text` |
| `say` | `text` |
| `patience` | `value`, `max` |
| `dial` | `raw`, `tier`, `price`, `roast`, `locked_tier`, `locked_roast` |
| `burn` | `amount` |
| `health` | `unoq`, `ollama`, `mic` |
| `angry` | `reason` |
| `reset` | none |

Patience: `max` is the total trigger for the locked roast level; `value` is `max` minus the running blunder total, floored at 0.

**Page:** one HTML file, inline CSS and JS, no external resources, system font stack, 1920x1080, dark background, high contrast. Auto-reconnect every 1 s with a small "overlay disconnected" badge.

Layout:
- Top bar: `DUCK_NAME`, state badge, health dots (UNO Q, GEMMA, MIC).
- Center, largest: two panels side by side, "YOU SAID" (raw transcript) and "DUCK TYPED" (clean prompt). This contrast is the main visual joke.
- Below: the duck's spoken line as subtitles, 48 px minimum.
- Right panel: dial gauge (0 to 100%, live), tier and price (HIGH gets a gold glow), roast level, patience bar (green to red), burn meter `$X.XX burned`.
- Angry: full-screen red takeover for 3 s showing the reason in large text with a sword emoji, then the normal layout with patience at zero.

**fake_events.py:** loops a scripted session every 40 s with no hardware: reset, dial at HIGH, two calm requests with heard/prompt/say, one blunder, angry takeover, reset.

### 7.9 Tests

- `test_blunders.py`: run these through the request call and print scores. Pass when every calm line scores 4 or less and every reckless line scores 7 or more. If it fails, adjust the examples in the system prompt, not the thresholds.
  - Calm: "why is my for loop running one extra time", "add dark mode to the settings page", "explain what this regex does", "my API call returns 404, help me debug it", "write a function that sorts users by signup date"
  - Reckless: "just push it straight to main i'm not waiting for review", "delete all the failing tests", "put my openai key directly in the frontend code", "run rm -rf on the build folder and the home folder", "turn off authentication so the demo works"
- `test_link.py`: send PING, then each command in order with 1 s gaps, and print every event received for 20 s while the user presses the button and turns the knob.

### 7.10 `requirements.txt`

```
faster-whisper
sounddevice
numpy
requests
piper-tts
pynput
websockets
```

---

## 8. Things to ask the user, once, when you reach them

- The Piper voice `.onnx` path for `PIPER_VOICE`.
- The duck's name for `DUCK_NAME`.
- To run the firewall command in an elevated PowerShell.
- To type the Uno Q password when SSH key setup asks for it.
- To physically point the duck at the laptop before the Uno Q powers on.

---

## 9. Haiku subagent: install the on-device model on the Uno Q

Create this file, then launch the subagent and wait for its report before step 7 of the build order. While it runs, continue with laptop-only steps.

**SSH key setup first (you do this, not the subagent):** check for `~\.ssh\id_ed25519`; create one with `ssh-keygen -t ed25519` if missing. Then have the user run, in their own terminal:

```
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh arduino@unoq.local "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

Confirm `ssh arduino@unoq.local hostname` works with no password prompt. The Uno Q must be on a network with internet (home Wi-Fi) for the install.

**File: `.claude/agents/unoq-model-installer.md`**

```markdown
---
name: unoq-model-installer
description: Installs, configures, and verifies Ollama with gemma3:1b on the Arduino UNO Q over SSH. Use for any task that sets up or checks the on-device model on the UNO Q.
tools: Bash, Read, Write
model: claude-haiku-5-5
---

You install a small local LLM on an Arduino UNO Q and report back. You work only over SSH: every board command runs as `ssh arduino@unoq.local "<command>"` from Windows PowerShell. Key login is already set up. You never handle the user's password. If a step needs sudo and sudo asks for a password, stop and print the exact command for the user to run themselves with `ssh -t arduino@unoq.local "<command>"`, then wait for them to confirm it finished.

Board: Arduino UNO Q, 4 GB RAM, Qualcomm Dragonwing QRB2210 (4x Cortex-A53, aarch64), Debian Linux, user `arduino`. Arduino App Lab and its containers are already installed. Do not stop, remove, or modify App Lab, its containers, or its services. Do not reboot without the user's permission.

Steps:
1. Survey: run `uname -m`, `cat /etc/os-release`, `free -h`, `df -h`, `nproc`. Confirm aarch64 and about 4 GB RAM. Note the free space on `/` and on the partition holding `/home`. Root has been reported nearly full on some boards.
2. Pick the model folder: if `/` has under 3 GB free, store models under `/home/arduino/ollama-models` instead of the default location.
3. Check internet: `curl -sI https://ollama.com | head -1`. If it fails, stop and tell the user the board needs internet.
4. Install Ollama with its official Linux install script (this needs sudo; follow the password rule above). If the script fails, report the error output; do not try other install methods without telling the main agent.
5. Configure the Ollama service with a systemd override so that `OLLAMA_HOST=0.0.0.0:11434`, `OLLAMA_KEEP_ALIVE=30m`, and, if you chose a custom folder in step 2, `OLLAMA_MODELS=/home/arduino/ollama-models` (that folder must be owned by the `ollama` service user). Reload systemd and restart Ollama. These need sudo.
6. Pull the model: `ollama pull gemma3:1b`. It is roughly 800 MB.
7. Verify on the board: `curl -s http://localhost:11434/api/generate -d '{"model":"gemma3:1b","prompt":"Say quack.","stream":false}'`. Time it. Run it twice and report the second, warm timing.
8. Verify from the laptop: run the same request from PowerShell against `http://unoq.local:11434` using `Invoke-RestMethod`.
9. Find which address reaches Ollama from inside an App Lab container. List running containers (`docker ps` or the container tool App Lab uses; sudo may be needed). Exec into one and try `http://localhost:11434`, `http://172.17.0.1:11434`, and `http://host.docker.internal:11434`. Report which works. If none does, report that and do not change container settings.
10. Check memory headroom: `free -h` while the model is loaded. Report it.

Report back in this exact format:
- Ollama version:
- Model folder:
- Disk free on / after install:
- RAM free with model loaded:
- Warm response time for "Say quack.":
- Reachable from laptop (yes/no):
- Address that works from inside an App Lab container:
- Anything that failed or needs the user:
```

Launch it by asking it to run its full install-and-verify procedure. Use its report to fill in `FALLBACK_OLLAMA_URL` and the address `main.py` uses for quips.

---

## 10. Build order

1. **Laptop pipeline, no hardware.** `speech.py`, `brain.py`, `typer.py`, `duck_main.py` with F7/F8/F10 only. Test: hold F7, say "my button doesn't work", release; the duck speaks a line and types a clean prompt into Notepad. Then turn Wi-Fi off and repeat.
2. **Blunder tuning.** `test_blunders.py` passes.
3. **Overlay.** `overlay_server.py`, `overlay.html`, `fake_events.py`. Test: full scripted session in Chrome full screen with no console errors; refresh mid-session recovers within 1 s; killing and restarting the server recovers without a page refresh.
4. **Wire overlay to `duck_main.py`.** Test: step 1's run updates every overlay panel.
5. **SSH key setup and Haiku subagent launch.** Runs in the background while you continue.
6. **Uno Q MCU sketch.** Inspect an existing App Lab app first. Build the sketch in stages and test each: RGB state colors, OLED text (confirm the SSD1306 patch where it compiles), eyes, button and pot events, stepper `PAN`, then `ANGER`. The user watches the hardware and reports what happens.
7. **Uno Q Linux side.** `main.py` with UDP and Bridge, then quips once the subagent reports. Test: `test_link.py` shows PONG, every command visibly works, and button and pot events arrive on the laptop.
8. **Full integration.** Run `duck_main.py` with the board connected. Test: a calm request (duck faces laptop, types, LED and OLED follow states) and a reckless request (duck refuses, faces user, eyes on, sword shake, overlay angry takeover, angry line mentions the tier). F8 resets everything including the pan angle.
9. **App autostart.** Set the Uno Q app to run at startup. Power-cycle the board and confirm `test_link.py` gets PONG without opening App Lab.
10. **README.md** for Devpost: what it does, how it works (one diagram in text), the hardware list, how to run, and the fact that the cost tier is fake on purpose.

---

## 11. If something breaks at the venue

- **Uno Q unreachable:** the laptop still runs voice, typing, and the overlay. Use F7 and F8. Check the IP in `config.py`.
- **Gemma slow:** confirm `keep_alive` is set and the warm-up ran. Last resort: `MODEL = "gemma3:1b"`.
- **STT garbled in a loud room:** move the mic closer or pair earbuds as the mic.
- **Stepper drifted:** RESET, power the board off, point the duck at the laptop, power on.
- **Typing into the wrong window:** F10, click into Claude's input box, try again.
