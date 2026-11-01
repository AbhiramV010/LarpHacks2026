"""WebSocket hub on :8765. Rebroadcasts every event to all browsers; replays the cache to newcomers."""
import asyncio
import json
import logging

import websockets

logging.basicConfig(level=logging.INFO, format="[overlay] %(message)s")
log = logging.getLogger("overlay")

cache: dict[str, str] = {}
clients: set = set()


async def handler(ws):
    clients.add(ws)
    for msg in cache.values():
        await ws.send(msg)
    try:
        async for raw in ws:
            try:
                ev = json.loads(raw)
            except ValueError:
                continue
            if ev.get("type") == "reset":
                cache.clear()
            if ev.get("type") != "angry":  # the takeover must not replay on refresh
                cache[ev.get("type", "?")] = raw
            dead = []
            for c in clients:
                if c is ws:
                    continue
                try:
                    await c.send(raw)
                except Exception:
                    dead.append(c)
            for c in dead:
                clients.discard(c)
    except Exception:
        pass
    finally:
        clients.discard(ws)


async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        log.info("ws://localhost:8765 — open overlay.html in a browser")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
