"""Real-world check of the one-click local AI (CI job `ollama-real`, any OS):
download + install the official Ollama, start it, pull a small model, summarize through REKORD's provider.

Run: python scripts/ollama_smoke.py [model]   (default qwen3:0.6b, ~500 MB)
"""
import sys
import time

sys.path.insert(0, __import__("os").path.dirname(__file__) + "/..")
from rekord.llm import ollama, providers  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:0.6b"
t0 = time.time()
print("installed before:", ollama.binary())
if not ollama.binary():
    last = [0.0]

    def progress(done, total):
        if time.time() - last[0] > 5:
            last[0] = time.time()
            print(f"  download {done / 1e6:.0f} / {total / 1e6:.0f} MB", flush=True)
    ollama.install(progress)
print("installed:", ollama.binary(), f"({time.time() - t0:.0f}s)")
assert ollama.start(wait=120), "Ollama did not start"
st = ollama.status()
print("running:", st["running"], "version:", st["version"], "ram:", st["ram_gb"], "default:", st["default"])
ollama._pull_blocking(model, None)
assert model in {m["name"] for m in ollama.status()["models"]}, ollama.status()["models"]
s = {"llm": {"provider": "ollama", "ollama": {"base_url": "http://localhost:11434", "model": model, "num_ctx": 4096}}}
out = providers.complete(s, "Du fasst Meetings zusammen. Antworte auf Deutsch, kurz.",
                         [{"role": "user", "content": "Transkript: Anna: Wir launchen am Freitag. Ben: Ich mache die Slides."
                                                      " Fasse in zwei Stichpunkten zusammen."}], 400)
print("answer:", out[:400])
assert out.strip() and "<think>" not in out
print(f"OK in {time.time() - t0:.0f}s")
