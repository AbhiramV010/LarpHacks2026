UNOQ_HOST = "unoq.local"       # fallback: set the board's IP here
UNOQ_PORT = 5005
LAPTOP_EVENT_PORT = 5006
OVERLAY_WS = "ws://localhost:8765"
OLLAMA_URL = "http://localhost:11434"
FALLBACK_OLLAMA_URL = "http://unoq.local:11434"
MODEL = "gemma3:4b"
FALLBACK_MODEL = "gemma3:1b"
WHISPER_MODEL = "base.en"
# TTS: ElevenLabs when ELEVENLABS_API_KEY is set and reachable, else the Windows SAPI voice.
ELEVENLABS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"   # "George"; swap for any voice id
ELEVENLABS_MODEL = "eleven_flash_v2_5"
DUCK_NAME = "QUACKSWORTH"
SUBMIT = True                  # press Enter after typing the prompt
TYPE_DELAY_S = 0.015
PRE_TYPE_PAUSE_S = 1.5
