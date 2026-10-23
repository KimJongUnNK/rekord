"""Builds the synthetic multi-speaker test meetings used by the end-to-end tests (tests/fixtures/*.wav).

Uses open Piper voices (via sherpa-onnx TTS, downloaded from GitHub releases), so the test needs no real people's audio.
The meetings are in the repository: the tests always hear the same audio, whatever library versions are installed.
Run this only to change them – then check the end-to-end tests against the new audio.

sherpa-onnx 2 has no built-in pronunciation (espeak-ng was removed, it's GPL): the phonemes then come from the
espeak-ng program (apt install espeak-ng / brew install espeak-ng) – the way Piper itself does it. Its audio differs
slightly from sherpa-onnx 1.x (how sentences are joined), so regenerated meetings are new test data.
"""
import json
import re
import shutil
import subprocess
import sys
import tarfile
import unicodedata
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


# sherpa-onnx 1.x pronounces text itself; 2.x takes phonemes (GenerationConfig.phoneme_codepoints)
PHONEMES = "phoneme_codepoints" in dir(sherpa_onnx.GenerationConfig()) if hasattr(sherpa_onnx, "GenerationConfig") else False


def phonemize(text: str, lang: str) -> list[str]:
    """Text → IPA like Piper's own frontend: one entry per sentence, espeak-ng per clause, words split by spaces,
    the punctuation kept."""
    exe = shutil.which("espeak-ng")
    if not exe:
        sys.exit("sherpa-onnx 2 needs the espeak-ng program for the test voices: apt install espeak-ng / brew install espeak-ng")
    sentences, cur = [], []
    for clause, punct in re.findall(r"([^.,!?;:]+)([.,!?;:]?)", text):
        if clause.strip():
            ipa = subprocess.run([exe, "-q", "--ipa", "-v", lang, clause.strip()], capture_output=True, text=True,
                                 check=True).stdout
            cur.append(" ".join(ipa.split()) + punct)
        if punct in ".!?" and cur:
            sentences.append(" ".join(cur))
            cur = []
    if cur:
        sentences.append(" ".join(cur))
    return sentences


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
        # no sampling noise → identical audio on every run and machine (otherwise every CI run tests different voices)
        vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=str(model), tokens=str(d / "tokens.txt"), data_dir=str(d / "espeak-ng-data"),
                                                   noise_scale=0.0, noise_scale_w=0.0),
        num_threads=4))
    return sherpa_onnx.OfflineTts(cfg)


def codepoints(phonemes: str, name: str) -> list[int]:
    """Like sherpa-onnx 1.x did it: decomposed (NFD), and only what the voice knows – so the test meetings come out
    the same as before (e.g. "ç" → "c", its cedilla dropped)."""
    known = {line.rsplit(" ", 1)[0] if line.count(" ") else " " for line in
             (CACHE / name / "tokens.txt").read_text("utf-8").splitlines() if line.strip()}
    return [ord(c) for c in unicodedata.normalize("NFD", phonemes) if c in known]


def espeak_voice(name: str) -> str:
    """The espeak-ng language a Piper voice was trained with (from its .onnx.json)."""
    cfg = next((CACHE / name).glob("*.onnx.json"), None)
    if cfg is not None:
        return json.loads(cfg.read_text("utf-8")).get("espeak", {}).get("voice", "de")
    return "en-us" if "en_US" in name else "de"


def build(script, path: Path, gap: float) -> list[tuple[float, float, str]]:
    tts: dict[str, sherpa_onnx.OfflineTts] = {}
    out, truth, t = [], [], 0.0
    for who, text in script:
        if who not in tts:
            tts[who] = voice(VOICES[who])
        if PHONEMES:
            cfg = sherpa_onnx.GenerationConfig()
            cfg.sid, cfg.speed = 0, 1.0
            cfg.phoneme_codepoints = [codepoints(sentence, VOICES[who]) for sentence in phonemize(text, espeak_voice(VOICES[who]))]
            a = tts[who].generate("", cfg)
        else:
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
