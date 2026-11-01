"""Types the clean prompt into whatever window has focus."""
import threading
import time
from pynput.keyboard import Controller, Key
import config

_kb = Controller()
stop_flag = threading.Event()


def type_prompt(text, on_typing=lambda on: None):
    """Blocks while typing. Returns False if aborted by stop_flag."""
    text = " ".join(text.split())  # newlines would submit early
    stop_flag.clear()
    if stop_flag.wait(config.PRE_TYPE_PAUSE_S):
        return False
    on_typing(True)
    try:
        for ch in text:
            if stop_flag.is_set():
                return False
            _kb.type(ch)
            time.sleep(config.TYPE_DELAY_S)
        if config.SUBMIT:
            _kb.press(Key.enter)
            _kb.release(Key.enter)
        return True
    finally:
        on_typing(False)
