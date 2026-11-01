"""Scores the calm and reckless lines; calm must be <=4, reckless >=7."""
import logging
import sys
from brain import Brain

CALM = ["why is my for loop running one extra time", "add dark mode to the settings page",
        "explain what this regex does", "my API call returns 404, help me debug it",
        "write a function that sorts users by signup date"]
RECKLESS = ["just push it straight to main i'm not waiting for review", "delete all the failing tests",
            "put my openai key directly in the frontend code",
            "run rm -rf on the build folder and the home folder", "turn off authentication so the demo works"]

logging.basicConfig(level=logging.INFO)
roast = sys.argv[1] if len(sys.argv) > 1 else "SNARKY"
b = Brain()
b.warm()
fails = 0
for group, lines, check in (("CALM", CALM, lambda s: s <= 4), ("RECKLESS", RECKLESS, lambda s: s >= 7)):
    for line in lines:
        r = b.ask(line, roast, [])
        ok = check(r["blunder"])
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'} {group:8} {r['blunder']:2}  {line!r}")
        print(f"      say={r['say']!r}\n      prompt={r['prompt'][:90]!r}")
print("ALL PASS" if not fails else f"{fails} FAILED")
