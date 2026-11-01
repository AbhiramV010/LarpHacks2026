"""
duck_main.py
Skeleton brain script for the talking rubber duck.

The overlay integration lives at the bottom. Copy the send_event helper
and the startup block into your real duck_main.py.
"""

import asyncio
import json
import logging
import websockets

log = logging.getLogger(__name__)

OVERLAY_URI = "ws://localhost:8765"

# ─── Overlay helper ──────────────────────────────────────

async def send_event(ws, **event):
    """Send a single JSON event to the overlay server."""
    await ws.send(json.dumps(event))


async def connect_overlay():
    """
    Connect once to the overlay server at startup.
    Returns the websocket on success, or None if the server is not running.
    The duck never crashes because the overlay is down.
    """
    try:
        ws = await websockets.connect(OVERLAY_URI)
        log.info("Overlay connected at %s", OVERLAY_URI)
        return ws
    except OSError as exc:
        log.warning("Overlay not available (%s) — running without it.", exc)
        return None


# ─── Example usage (replace with real duck logic) ────────

async def run_duck():
    overlay = await connect_overlay()

    async def emit(**event):
        if overlay:
            try:
                await send_event(overlay, **event)
            except Exception as exc:
                log.warning("Overlay send failed: %s", exc)

    # Example sequence — replace with real duck logic
    await emit(type="reset")
    await emit(type="status", unoq=True, ollama=True, mic=True)
    await emit(type="tier", tier="medium")
    await emit(type="state", state="idle")

    # ... rest of the duck brain


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_duck())
