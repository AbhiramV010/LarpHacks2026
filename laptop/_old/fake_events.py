"""
fake_events.py
Plays a scripted duck session in a loop so the overlay can be tested
without any hardware or language model running.

Usage:
    python fake_events.py
"""

import asyncio
import json
import logging
import websockets

logging.basicConfig(level=logging.INFO, format="[fake] %(asctime)s %(message)s")
log = logging.getLogger(__name__)

SERVER_URI = "ws://localhost:8765"
LOOP_INTERVAL = 30  # seconds between sessions


async def send(ws, **event):
    await ws.send(json.dumps(event))
    await asyncio.sleep(0.05)


async def stream_text(ws, text: str, final_delay: float = 0.12):
    """Send duck_text events word by word, ending with final=True."""
    words = text.split()
    accumulated = ""
    for i, word in enumerate(words):
        accumulated += ("" if i == 0 else " ") + word
        is_final = i == len(words) - 1
        await send(ws, type="duck_text", text=accumulated, final=is_final)
        await asyncio.sleep(final_delay)


TURNS = [
    {
        "user": "I'm building an AI startup that disrupts dating apps",
        "duck": (
            "Let me get this straight — you're burning VC money to teach "
            "a large language model to say 'ur cute' on your behalf. "
            "Dating apps were already dystopian; congratulations on adding a new layer."
        ),
    },
    {
        "user": "But our AI matches people based on their values and vibe",
        "duck": (
            "Values. Vibe. You scraped their Instagram, ran it through an embedding, "
            "and called the cosine similarity 'compatibility'. "
            "That's not connection, that's vector math with feelings."
        ),
    },
    {
        "user": "We have 10 000 waitlist signups and a Y-Combinator interview next week",
        "duck": (
            "Ten thousand people gave you their email so they didn't have to think "
            "about dating for five minutes. YC will ask about retention. "
            "You will say 'growth'. They will pass."
        ),
    },
]

VERDICT_TEXT = (
    "Diagnosis: larper. Also, that dial does nothing. You paid for vibes."
)


async def play_session(ws):
    log.info("--- Starting session ---")

    # 1. Reset & initialise
    await send(ws, type="reset")
    await asyncio.sleep(0.2)
    await send(ws, type="status", unoq=True, ollama=True, mic=True)
    await send(ws, type="tier", tier="high")
    await send(ws, type="state", state="idle")
    await asyncio.sleep(2)

    max_turns = len(TURNS)

    for i, turn_data in enumerate(TURNS):
        turn_n = i + 1

        # Listening
        await send(ws, type="state", state="listening")
        await asyncio.sleep(1.5)
        await send(ws, type="user_text", text=turn_data["user"])
        await asyncio.sleep(0.5)

        # Thinking
        await send(ws, type="state", state="thinking")
        await asyncio.sleep(2)

        # Talking
        await send(ws, type="state", state="talking")
        await send(ws, type="turn", n=turn_n, max=max_turns)
        await stream_text(ws, turn_data["duck"])
        await asyncio.sleep(1.5)

    # Verdict
    await send(ws, type="state", state="verdict")
    await stream_text(ws, VERDICT_TEXT, final_delay=0.10)
    await asyncio.sleep(4)

    # Leaving
    await send(ws, type="state", state="leaving")
    await asyncio.sleep(3)

    # Back to idle
    await send(ws, type="state", state="idle")
    log.info("--- Session complete. Next in %d s ---", LOOP_INTERVAL)


async def main():
    log.info("Connecting to %s", SERVER_URI)
    while True:
        try:
            async with websockets.connect(SERVER_URI) as ws:
                log.info("Connected.")
                while True:
                    await play_session(ws)
                    await asyncio.sleep(LOOP_INTERVAL)
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            log.warning("Cannot reach server (%s). Retrying in 2 s…", exc)
            await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped.")
