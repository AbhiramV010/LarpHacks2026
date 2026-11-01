"""Sends every command to the Uno Q with 1 s gaps, then prints events for 20 s."""
import logging
import queue
import time
from link import Link

logging.basicConfig(level=logging.INFO)
CMDS = ["STATE listening", "STATE translating", "STATE typing", "TYPING 1", "TYPING 0",
        "STATE waiting", "STATE talking", "OLED hello|from laptop", "EYES 255", "EYES 0",
        "PAN 90", "PAN 0", "ANGER", "RESET"]

link = Link()
time.sleep(1.5)
print("Uno Q up:", link.up)
for c in CMDS:
    print(">", c)
    link.send(c)
    time.sleep(1)
print("Listening for events for 20 s: press the button, turn the knob")
end = time.time() + 20
while time.time() < end:
    try:
        print("<", link.events.get(timeout=0.5))
    except queue.Empty:
        pass
print("Uno Q up:", link.up)
