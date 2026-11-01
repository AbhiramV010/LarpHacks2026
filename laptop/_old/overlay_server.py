"""
overlay_server.py
WebSocket hub for the Duck Status Overlay.

The brain script (duck_main.py) connects as a client and sends JSON events.
This server rebroadcasts each event to every connected browser and keeps the
latest value of each event type so a browser that connects or refreshes
mid-session gets the current state immediately.

Usage:
    python overlay_server.py
"""

import asyncio
import json
import logging
import websockets

logging.basicConfig(level=logging.INFO, format="[overlay] %(asctime)s %(message)s")
log = logging.getLogger(__name__)

HOST = "localhost"
PORT = 8765

# Latest snapshot of every event type received so far.
# When a new browser connects it gets all of these immediately.
state_cache: dict[str, dict] = {}

# All currently connected browser clients (not the brain).
# The brain is identified by a "source: brain" field in its first message,
# or we treat every sender as a potential broadcaster.
clients: set = set()


async def handler(websocket):
    """Handle one WebSocket connection (browser or brain)."""
    clients.add(websocket)
    remote = websocket.remote_address
    log.info("Client connected: %s  (total=%d)", remote, len(clients))

    # Send current cached state to the newly connected client immediately.
    if state_cache:
        snapshot = list(state_cache.values())
        try:
            await websocket.send(json.dumps({"type": "snapshot", "events": snapshot}))
        except Exception:
            pass

    try:
        async for raw in websocket:
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Bad JSON from %s: %r", remote, raw[:120])
                continue

            etype = event.get("type")
            if etype:
                state_cache[etype] = event

            # Rebroadcast to every OTHER connected client.
            dead = set()
            for client in clients:
                if client is websocket:
                    continue
                try:
                    await client.send(raw)
                except Exception:
                    dead.add(client)
            clients.difference_update(dead)

    except websockets.exceptions.ConnectionClosedOK:
        pass
    except websockets.exceptions.ConnectionClosedError as exc:
        log.warning("Connection closed with error from %s: %s", remote, exc)
    finally:
        clients.discard(websocket)
        log.info("Client disconnected: %s  (total=%d)", remote, len(clients))


async def main():
    log.info("Starting overlay server on ws://%s:%d", HOST, PORT)
    async with websockets.serve(handler, HOST, PORT):
        log.info("Server ready. Press Ctrl-C to stop.")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutting down.")
