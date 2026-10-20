"""Pairing phones and other devices in the Wi-Fi.

The computer shows a 6-digit code (e.g. 482 913) that's easy to type or read out. It's valid for 10 minutes and
only for pairing: a device that enters it gets its own long key, which it uses from then on. Each device can be
disconnected on its own; "Alle Geräte trennen" makes every key invalid. 5 wrong tries lock that device out for a
minute, and after 30 wrong tries in total the code is replaced – 6 digits can't be guessed through the Wi-Fi.
The QR code still carries the long shared key (scanning needs to be at the computer anyway)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time

from . import config

CODE_TTL = 600
MAX_TRIES = 5
LOCK_SECONDS = 60
MAX_TOTAL_FAILS = 30

_lock = threading.Lock()
_code: dict = {"code": "", "expires": 0.0, "fails": 0}
_tries: dict[str, tuple[int, float]] = {}  # client → (wrong tries, locked until)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_code() -> dict:
    """The code to show on the computer ({"code": "482913", "expires": unix time}), renewed when it runs out."""
    with _lock:
        if not _code["code"] or time.time() >= _code["expires"]:
            _new_code()
        return {"code": _code["code"], "expires": _code["expires"]}


def new_code() -> dict:
    with _lock:
        _new_code()
        return {"code": _code["code"], "expires": _code["expires"]}


def _new_code() -> None:
    _code.update(code=f"{secrets.randbelow(10**6):06d}", expires=time.time() + CODE_TTL, fails=0)


def normalize(code: str) -> str:
    return "".join(ch for ch in str(code) if ch.isdigit())


def claim(code: str, client: str, name: str = "") -> str:
    """Code from the device → its own key. Raises PermissionError with a readable reason."""
    now = time.time()
    with _lock:
        fails, until = _tries.get(client, (0, 0.0))
        if until > now:
            raise PermissionError(f"Zu viele falsche Versuche – in {int(until - now) + 1} s nochmal.")
        valid = bool(_code["code"]) and now < _code["expires"]
        if not valid or not hmac.compare_digest(normalize(code), _code["code"]):
            fails += 1
            _tries[client] = (0, now + LOCK_SECONDS) if fails >= MAX_TRIES else (fails, 0.0)
            _code["fails"] += 1
            if _code["fails"] >= MAX_TOTAL_FAILS:  # someone keeps guessing: this code is burnt
                _new_code()
            raise PermissionError("Code abgelaufen – am Computer steht ein neuer." if not valid and _code["code"]
                                  else "Falscher Code. Er steht am Computer unter Einstellungen → iPhone & Geräte.")
        _tries.pop(client, None)
    token = secrets.token_urlsafe(24)
    devices = list(config.load().get("devices") or [])
    devices.append({"id": secrets.token_hex(4), "name": (name or "Gerät").strip()[:40], "hash": _hash(token),
                    "created": round(now)})
    config.save({"devices": devices})
    return token


def token_ok(token: str | None) -> bool:
    """The shared key (QR code) or a device's own key."""
    if not token:
        return False
    s = config.load()
    if hmac.compare_digest(token.encode(), s["pair_token"].encode()):
        return True
    h = _hash(token)
    return any(hmac.compare_digest(h, d.get("hash", "")) for d in s.get("devices") or [])


def devices() -> list[dict]:
    return [{k: d[k] for k in ("id", "name", "created") if k in d} for d in config.load().get("devices") or []]


def remove(device_id: str) -> bool:
    devs = list(config.load().get("devices") or [])
    keep = [d for d in devs if d.get("id") != device_id]
    if len(keep) == len(devs):
        return False
    config.save({"devices": keep})
    return True


def disconnect_all() -> None:
    """New shared key, no device keys, new code: every device has to pair again."""
    config.save({"pair_token": secrets.token_urlsafe(18), "devices": []})
    new_code()


def device_name(user_agent: str) -> str:
    ua = user_agent or ""
    for key, label in (("REKORD-iOS", "iPhone-App"), ("CFNetwork", "iPhone-App"), ("iPhone", "iPhone"), ("iPad", "iPad"),
                       ("Android", "Android"), ("Macintosh", "Mac"), ("Windows", "Windows-PC"), ("Linux", "Linux")):
        if key in ua:
            return label
    return "Gerät"
