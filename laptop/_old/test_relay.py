"""
Self-contained relay test — exits cleanly after assertions.
"""
import asyncio, json, sys
import websockets

HOST = "localhost"
PORT = 8766

state_cache: dict = {}
clients: set = set()

async def handler(ws):
    clients.add(ws)
    if state_cache:
        await ws.send(json.dumps({"type": "snapshot", "events": list(state_cache.values())}))
    try:
        async for raw in ws:
            ev = json.loads(raw)
            state_cache[ev.get("type")] = ev
            dead = set()
            for c in clients:
                if c is ws: continue
                try: await c.send(raw)
                except: dead.add(c)
            clients.difference_update(dead)
    except Exception:
        pass
    finally:
        clients.discard(ws)


async def run_tests(stop_event):
    brain   = await websockets.connect(f"ws://{HOST}:{PORT}")
    browser = await websockets.connect(f"ws://{HOST}:{PORT}")

    # Drain potential snapshot (empty cache, so nothing should arrive)
    try:
        await asyncio.wait_for(browser.recv(), timeout=0.3)
    except asyncio.TimeoutError:
        pass

    # Test 1: relay
    await brain.send(json.dumps({"type": "state", "state": "listening"}))
    msg = await asyncio.wait_for(browser.recv(), timeout=3)
    ev = json.loads(msg)
    assert ev == {"type": "state", "state": "listening"}, f"FAIL relay: {ev}"
    print("RELAY TEST PASSED:", ev, flush=True)

    # Test 2: snapshot for late joiner
    browser2 = await websockets.connect(f"ws://{HOST}:{PORT}")
    snap_raw = await asyncio.wait_for(browser2.recv(), timeout=3)
    snap = json.loads(snap_raw)
    assert snap["type"] == "snapshot", f"FAIL snapshot type: {snap}"
    assert any(e.get("state") == "listening" for e in snap["events"]), f"FAIL snapshot content: {snap}"
    print("SNAPSHOT TEST PASSED:", snap, flush=True)

    await brain.close()
    await browser.close()
    await browser2.close()

    print("ALL TESTS PASSED", flush=True)
    stop_event.set()


async def main():
    stop = asyncio.Event()
    server = await websockets.serve(handler, HOST, PORT)
    try:
        await run_tests(stop)
        await asyncio.wait_for(stop.wait(), timeout=5)
    finally:
        server.close()
        await server.wait_closed()


asyncio.run(main())
