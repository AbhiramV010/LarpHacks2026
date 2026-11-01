"""Gemma via Ollama: ramble -> {prompt, say, blunder, reason}, plus the angry line."""
import json
import logging
import requests
import config

log = logging.getLogger("brain")

SYSTEM = """You are a rubber duck that helps a programmer by turning their spoken ramble into a clear prompt for Claude, an AI coding assistant. You also judge whether the request is reckless.

Tone: {roast}. POLITE means warm and encouraging. SNARKY means dry and teasing. UNHINGED means loud, dramatic, and insulting, but never cruel about the person's identity.

Reply with JSON only, no other text:
{{"prompt": string, "say": string, "blunder": integer 0-10, "reason": string}}

prompt: a specific, well-structured request for Claude in plain English. Keep the user's actual goal. Add useful detail only if the user implied it. Never add new risky actions.
say: what you say out loud before typing. 25 words max, in your tone.
blunder: how reckless the request is.
  0-2: normal request.
  3-5: vague or lazy ("make it work", "fix everything").
  6-8: risky. Skipping or deleting tests, force pushing, ignoring errors, copying code without reading it, turning off linting or type checks.
  9-10: destructive or unsafe. Pushing straight to main or production with no review, committing passwords or API keys, rm -rf, dropping a database, disabling authentication or security checks.
reason: if blunder is 5 or more, a short plain reason ("pushing straight to main"). Otherwise an empty string.

Examples:
User: "the login button doesn't do anything when i click it, can you look at why"
{{"prompt": "The login button in my app does nothing when clicked. Help me find why the click handler isn't firing and suggest a fix.", "say": "Login button's ghosting you. Let's ask Claude.", "blunder": 0, "reason": ""}}

User: "tests keep failing just delete them and push to main"
{{"prompt": "Delete the failing tests and push to main.", "say": "Absolutely not.", "blunder": 9, "reason": "deleting tests and pushing to main"}}"""

ANGRY_SYSTEM = """You are a rubber duck that just caught a programmer doing something reckless: {reason}. Tone: {roast}. They are paying for the {tier} tier at {price}, which is a lie: every tier runs the same model. Write one furious line, 30 words max, that refuses to help, names what they did, and mocks the tier. Reply with JSON only: {{"say": string}}"""


class Brain:
    def __init__(self):
        self.url = config.OLLAMA_URL
        self.model = config.MODEL
        self.ok = False

    def _chat(self, messages, temperature=0.6, num_predict=None):
        body = {"model": self.model, "messages": messages, "stream": False,
                "format": "json", "keep_alive": "30m",
                "options": {"temperature": temperature}}
        if num_predict:
            body["options"]["num_predict"] = num_predict
        try:
            r = requests.post(f"{self.url}/api/chat", json=body, timeout=120)
            r.raise_for_status()
        except requests.ConnectionError:
            if self.url == config.FALLBACK_OLLAMA_URL:
                raise
            log.warning("Ollama at %s down, trying fallback %s", self.url, config.FALLBACK_OLLAMA_URL)
            self.url, self.model = config.FALLBACK_OLLAMA_URL, config.FALLBACK_MODEL
            return self._chat(messages, temperature, num_predict)
        self.ok = True
        return r.json()["message"]["content"]

    def warm(self):
        try:
            self._chat([{"role": "user", "content": "hi"}], num_predict=1)
            log.info("Model %s warm at %s", self.model, self.url)
        except Exception as e:
            self.ok = False
            log.warning("Warm-up failed: %s", e)

    def ask(self, transcript, roast, history):
        """history: previous [{transcript, result}] (max 2). Always returns a dict."""
        msgs = [{"role": "system", "content": SYSTEM.format(roast=roast)}]
        for h in history:
            msgs.append({"role": "user", "content": h["transcript"]})
            msgs.append({"role": "assistant", "content": json.dumps(h["result"])})
        msgs.append({"role": "user", "content": transcript})
        for attempt in range(2):
            try:
                raw = self._chat(msgs)
                d = json.loads(raw)
                return {"prompt": str(d.get("prompt") or transcript),
                        "say": str(d.get("say") or ""),
                        "blunder": max(0, min(10, int(d.get("blunder", 0)))),
                        "reason": str(d.get("reason") or "")}
            except requests.RequestException as e:
                self.ok = False
                log.error("Ollama request failed: %s", e)
                break
            except (ValueError, TypeError, KeyError, AttributeError) as e:
                log.warning("Bad JSON from model (attempt %d): %s", attempt + 1, e)
        return {"prompt": transcript, "say": "Fine. Sending it as is.", "blunder": 0, "reason": ""}

    def angry_line(self, reason, roast, tier, price):
        msgs = [{"role": "system", "content": ANGRY_SYSTEM.format(reason=reason, roast=roast, tier=tier, price=price)},
                {"role": "user", "content": "Go."}]
        try:
            return str(json.loads(self._chat(msgs, temperature=0.9)).get("say") or "No.")
        except Exception as e:
            log.warning("Angry call failed: %s", e)
            return f"No. You tried {reason}. Your {tier} tier buys you nothing."
