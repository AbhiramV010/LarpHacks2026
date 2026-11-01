"""Uno Q Linux side: UDP :5005 -> Bridge "cmd"; Bridge "event" -> UDP laptop:5006; OLED quips from local Gemma."""
import json
import socket
import threading
import time
import urllib.request

from arduino.app_utils import App, Bridge

# Address of the board's Ollama as seen from inside the App Lab container.
# Replace with the one the unoq-model-installer subagent reports (e.g. http://172.17.0.1:11434).
OLLAMA = "http://localhost:11434"
QUIP_MODEL = "gemma3:1b"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 5005))
sock.setblocking(False)
laptop = None  # (ip, 5006), learned from the first packet
quip_lock = threading.Lock()


def on_event(text):
    """MCU -> laptop."""
    if laptop:
        try:
            sock.sendto(str(text).encode("utf-8"), laptop)
        except OSError:
            pass


def quip():
    """Ask the on-device model for a 16-char duck one-liner; send it as OLED line 2."""
    if not quip_lock.acquire(blocking=False):
        return
    try:
        body = json.dumps({"model": QUIP_MODEL, "stream": False, "keep_alive": "30m",
                           "options": {"temperature": 1.0, "num_predict": 12},
                           "prompt": "You are a sarcastic rubber duck watching a programmer. Write one "
                                     "lowercase one-liner of at most 16 characters, like 'quack. ship it.' "
                                     "or 'tests? optional'. Reply with the line only."}).encode()
        req = urllib.request.Request(f"{OLLAMA}/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            line = json.loads(r.read())["response"].strip().strip('"').splitlines()[0][:16]
        if line:
            Bridge.call("cmd", f"LINE2 {line}")
    except Exception:
        pass  # timeout or model down: leave line 2 unchanged
    finally:
        quip_lock.release()


def loop():
    global laptop
    try:
        data, addr = sock.recvfrom(1024)
    except BlockingIOError:
        time.sleep(0.01)
        return
    text = data.decode("utf-8", "replace").strip()
    laptop = (addr[0], 5006)
    if text == "PING":
        sock.sendto(b"PONG", laptop)
        return
    Bridge.call("cmd", text)
    if text in ("STATE idle", "STATE waiting"):
        threading.Thread(target=quip, daemon=True).start()


Bridge.provide("event", on_event)
App.run(user_loop=loop)
