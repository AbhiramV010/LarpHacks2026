"""One Notepad window the duck owns: open it, focus it, read its text back via the clipboard."""
import logging
import subprocess
import time

from pynput.keyboard import Controller, Key

log = logging.getLogger("notepad")
_kb = Controller()
_proc = None


def is_open():
    return _proc is not None and _proc.poll() is None


def open_and_focus():
    global _proc
    if not is_open():
        _proc = subprocess.Popen(["notepad.exe"])
        time.sleep(1.0)
    assert _proc is not None
    _ps("(New-Object -ComObject WScript.Shell).AppActivate($args[0])", str(_proc.pid))


def select_all():
    """Ctrl+A in the focused Notepad, so the next typing replaces its text."""
    _hotkey("a")
    time.sleep(0.1)


def read_current():
    """Ctrl+A, Ctrl+C in the focused Notepad, then read the clipboard. Returns '' on any failure."""
    try:
        open_and_focus()
        time.sleep(0.4)
        _hotkey("a")
        _hotkey("c")
        time.sleep(0.2)
        out = _ps("Get-Clipboard -Raw")
        _kb.press(Key.right)  # drop the selection so nothing gets overwritten by accident
        _kb.release(Key.right)
        return out.replace("\r\n", "\n").strip()
    except Exception as e:
        log.warning("Could not read Notepad: %s", e)
        return ""


def _hotkey(letter):
    with _kb.pressed(Key.ctrl):
        _kb.press(letter)
        _kb.release(letter)


def _ps(script, *args):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", script, *args],
                       capture_output=True, text=True, timeout=10)
    return r.stdout
