"""Loops a scripted duck session every 40 s so the overlay can be tested with no hardware."""
import asyncio
import json

import websockets
import config


async def session(ws):
    async def ev(type_, **f):
        await ws.send(json.dumps({"type": type_, **f}))

    async def dial(raw):
        await ev("dial", raw=raw, tier="HIGH", price="PREMIUM $49.99/mo", roast="UNHINGED",
                 locked_tier="HIGH", locked_roast="UNHINGED")

    await ev("reset")
    await ev("state", state="idle")
    await ev("health", unoq=True, ollama=True, mic=True)
    for raw in range(0, 900, 100):
        await dial(raw)
        await asyncio.sleep(0.1)
    await ev("patience", value=8, max=8)
    await ev("burn", amount=0.0)

    turns = [
        ("uh so the login button like doesn't do anything when i click it and i dont know why",
         "The login button in my app does nothing when clicked. Help me find why the click handler isn't firing and suggest a fix.",
         "LOGIN BUTTON'S GHOSTING YOU. Hold on, I'll translate your mumbling for Claude.", 1, 7),
        ("make it work idk just fix everything",
         "Review the current failing behaviour, identify the root cause, and propose a fix.",
         "'FIX EVERYTHING'. Incredible. Pulitzer-worthy prompt. Let me translate from Caveman.", 4, 3),
    ]
    burn = 0.0
    for heard, prompt, say, _score, patience in turns:
        await ev("state", state="listening")
        await asyncio.sleep(2)
        await ev("state", state="translating")
        await ev("heard", text=heard)
        await asyncio.sleep(1.5)
        burn += 4.20
        await ev("burn", amount=round(burn, 2))
        await ev("patience", value=patience, max=8)
        await ev("prompt", text=prompt)
        await ev("state", state="talking")
        await ev("say", text=say)
        await asyncio.sleep(3)
        await ev("state", state="typing")
        await asyncio.sleep(3)
        await ev("state", state="waiting")
        await asyncio.sleep(1)
        await ev("state", state="idle")
        await asyncio.sleep(2)

    await ev("state", state="listening")
    await asyncio.sleep(2)
    await ev("state", state="translating")
    await ev("heard", text="tests keep failing just delete them and push straight to main")
    await asyncio.sleep(1.5)
    await ev("prompt", text="Delete the failing tests and push to main.")
    await ev("patience", value=0, max=8)
    await ev("state", state="angry")
    await ev("angry", reason="deleting tests and pushing to main")
    await ev("say", text="ABSOLUTELY NOT. You deleted the TESTS and want MAIN? Your PREMIUM $49.99 tier bought you the exact same model and zero judgment.")
    await asyncio.sleep(8)
    await ev("reset")
    await ev("state", state="idle")
    await ev("patience", value=8, max=8)


async def main():
    while True:
        try:
            async with websockets.connect(config.OVERLAY_WS) as ws:
                while True:
                    await session(ws)
                    await asyncio.sleep(12)
        except Exception as e:
            print("overlay server not reachable:", e)
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
