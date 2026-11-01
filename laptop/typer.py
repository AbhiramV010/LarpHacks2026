"""Types the clean prompt into whatever window has focus."""
import threading
import time
from pynput.keyboard import Controller, Key
import config

_kb = Controller()
stop_flag = threading.Event()


def type_prompt(text, on_typing=lambda on: None, code=False):
    """Blocks while typing. code=True keeps newlines (as Enter) and does not submit. Returns False if aborted."""
    if not code:
        text = " ".join(text.split())  # newlines would submit early
    stop_flag.clear()
    if stop_flag.wait(config.PRE_TYPE_PAUSE_S):
        return False
    on_typing(True)
    try:
        for ch in text:
            if stop_flag.is_set():
                return False
            if ch == "\n":
                _kb.press(Key.enter)
                _kb.release(Key.enter)
            else:
                _kb.type(ch)
            time.sleep(config.TYPE_DELAY_S)
        if config.SUBMIT and not code:
            _kb.press(Key.enter)
            _kb.release(Key.enter)
        return True
    finally:
        on_typing(False)
