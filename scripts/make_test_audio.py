"""Builds the synthetic multi-speaker test meetings used by the end-to-end tests (tests/fixtures/*.wav).

Uses open Piper voices (via sherpa-onnx TTS, downloaded from GitHub releases), so the test needs no real people's audio.
"""
import sys
import tarfile
import urllib.request
from pathlib import Path

import numpy as np
import sherpa_onnx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rekord.audio import write_wav  # noqa: E402
from rekord.live import resample  # noqa: E402

CACHE = ROOT / "tests" / ".tts"
OUT = ROOT / "tests" / "fixtures"
BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models"
VOICES = {"A": "vits-piper-de_DE-thorsten-medium", "B": "vits-piper-de_DE-kerstin-low",
          "C": "vits-piper-en_US-ryan-medium", "D": "vits-piper-de_DE-eva_k-x_low"}

MEETING1 = [
    ("A", "Guten Morgen zusammen. Heute besprechen wir das Budget für das Sommerfestival und die Bühnenplanung."),
    ("B", "Danke. Ich habe die Angebote von drei Technikfirmen eingeholt. Das günstigste liegt bei achttausend Euro."),
    ("A", "Das ist mehr als geplant. Können wir beim Licht sparen, ohne dass die Show leidet?"),
    ("B", "Ja, wenn wir die LED Wände nur auf der Hauptbühne einsetzen, sparen wir ungefähr zweitausend Euro."),
    ("C", "Quick note from my side. The headliner confirmed the date, but they need the rider signed by Friday."),
    ("A", "Perfekt. Dann übernehme ich den Rider bis Freitag, und du schickst die Technik Bestellung raus."),
    ("B", "Mach ich. Ich schicke die Bestellung morgen bis zwölf Uhr."),
]
MEETING2 = [
    ("B", "Kurzes Update zur Location. Der Vertrag mit der Halle ist unterschrieben, wir haben den Termin im August fix."),
    ("D", "Super. Ich kümmere mich um das Catering. Wir brauchen noch eine Zahl, wie viele Gäste wir erwarten."),
    ("A", "Wir planen mit zwölfhundert Gästen. Das Ticketing startet nächste Woche Montag."),
    ("D", "Okay, dann bestelle ich für zwölfhundert und frage nach veganen Optionen."),
    ("B", "Und denk an die Getränkelizenz, die muss bis Ende des Monats beim Amt sein."),
]


def voice(name: str) -> sherpa_onnx.OfflineTts:
    d = CACHE / name
    if not d.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        tgz = CACHE / f"{name}.tar.bz2"
        print("download", name)
        urllib.request.urlretrieve(f"{BASE}/{name}.tar.bz2", tgz)
        with tarfile.open(tgz, "r:bz2") as t:
            t.extractall(CACHE, filter="data")
        tgz.unlink()
    model = next(d.glob("*.onnx"))
    cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
        vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=str(model), tokens=str(d / "tokens.txt"), data_dir=str(d / "espeak-ng-data")),
        num_threads=4))
    return sherpa_onnx.OfflineTts(cfg)


def build(script, path: Path, gap: float) -> list[tuple[float, float, str]]:
    tts: dict[str, sherpa_onnx.OfflineTts] = {}
    out, truth, t = [], [], 0.0
    for who, text in script:
        if who not in tts:
            tts[who] = voice(VOICES[who])
        a = tts[who].generate(text, sid=0, speed=1.0)
        x = resample(np.array(a.samples, dtype=np.float32), a.sample_rate, 16000)
        out += [x, np.zeros(int(16000 * gap), dtype=np.float32)]
        truth.append((t, t + len(x) / 16000, who))
        t += len(x) / 16000 + gap
    write_wav(path, np.concatenate(out))
    return truth


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    build(MEETING1, OUT / "meeting1.wav", 0.6)
    build(MEETING2, OUT / "meeting2.wav", 0.5)
    print("fixtures ->", OUT)
