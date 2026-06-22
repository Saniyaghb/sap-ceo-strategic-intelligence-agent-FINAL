import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ollama
from config import OLLAMA_MODEL

try:
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": "Reply with: Ollama is working."}],
    )
    print(response["message"]["content"])
except Exception as exc:
    print("Ollama test failed. Make sure Ollama is running and the model is pulled.")
    print(exc)
