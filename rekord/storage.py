"""Where REKORD keeps its things: the data folder (recordings, database, voiceprints) and the models folder
(speech models + local AI). Lists the drives of this computer – built-in, external (USB/Thunderbolt), extra SSD/NVMe,
network (NAS) – and moves everything over with progress. Moving the data folder ends with a restart."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import threading
import time
from pathlib import Path

from . import config, system

KIND_LABEL = {"internal": "Eingebaut", "external": "Extern (USB/Thunderbolt)", "nvme": "SSD / NVMe", "network": "Netzwerk (NAS)",
              "removable": "Wechseldatenträger"}

_job: dict = {"state": "idle", "what": "", "done": 0, "total": 0, "error": "", "restart": False}
_lock = threading.Lock()


# ------------------------------------------------------------------ sizes

def free_gb(path: Path) -> float | None:
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        return round(shutil.disk_usage(p).free / 1e9, 1)
    except OSError:
        return None


def size_bytes(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def ollama_default_dir() -> Path:
    return Path(os.environ.get("OLLAMA_MODELS") or Path.home() / ".ollama" / "models")


def ollama_dir() -> Path:
    return config.ollama_models_dir() or ollama_default_dir()


# ------------------------------------------------------------------ drives

def _drive(path: str, name: str, kind: str, total: int | None = None) -> dict | None:
    try:
        u = shutil.disk_usage(path)
    except OSError:
        return None
    return {"path": path, "name": name, "kind": kind, "kind_label": KIND_LABEL.get(kind, kind),
            "free_gb": round(u.free / 1e9, 1), "total_gb": round((total or u.total) / 1e9, 1),
            "writable": os.access(path, os.W_OK)}


def _mac_drives() -> list[dict]:
    import plistlib
    out = [_drive(str(Path.home()), "Dieser Mac", "internal")]
    vols = Path("/Volumes")
    for v in sorted(vols.iterdir()) if vols.exists() else []:
        if v.is_symlink() or v.name.startswith("."):  # "Macintosh HD" → /
            continue
        kind = "external"
        try:
            info = plistlib.loads(system.run(["diskutil", "info", "-plist", str(v)], 10).stdout.encode())
            proto = str(info.get("BusProtocol") or info.get("Protocol") or "")
            if info.get("Internal") and not info.get("RemovableMedia"):
                kind = "nvme" if "PCI" in proto else "internal"
            if not info.get("DeviceNode"):  # smbfs/afpfs/nfs
                kind = "network"
        except Exception:  # noqa: BLE001 - diskutil not available or unknown volume: treat as external
            pass
        out.append(_drive(str(v), v.name, kind))
    return [d for d in out if d]


def _windows_drives() -> list[dict]:
    import ctypes
    import string
    bus = {}
    try:  # BusType per drive letter: USB / NVMe / SATA / …
        r = system.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                        "Get-Partition | Where-Object DriveLetter | ForEach-Object { $d = $_ | Get-Disk; "
                        "[pscustomobject]@{L=[string]$_.DriveLetter; B=[string]$d.BusType} } | ConvertTo-Json"], 20)
        data = json.loads(r.stdout or "[]")
        for x in data if isinstance(data, list) else [data]:
            bus[x["L"].upper()] = x["B"]
    except Exception:  # noqa: BLE001
        pass
    sysdrive = os.environ.get("SystemDrive", "C:").rstrip("\\").upper()
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    out = []
    for i, letter in enumerate(string.ascii_uppercase):
        if not mask & (1 << i):
            continue
        root = f"{letter}:\\"
        t = ctypes.windll.kernel32.GetDriveTypeW(root)  # 2 removable, 3 fixed, 4 network, 5 cd
        if t not in (2, 3, 4):
            continue
        name = ctypes.create_unicode_buffer(261)
        ctypes.windll.kernel32.GetVolumeInformationW(root, name, 261, None, None, None, None, 0)
        b = bus.get(letter, "")
        kind = ("network" if t == 4 else "removable" if t == 2 else "external" if b == "USB"
                else "internal" if f"{letter}:" == sysdrive else "nvme" if b == "NVMe" else "internal")
        label = f"{name.value or ('Lokaler Datenträger' if t == 3 else 'Laufwerk')} ({letter}:)"
        out.append(_drive(str(Path.home()) if f"{letter}:" == sysdrive else root, label, kind))
    return [d for d in out if d]


def _linux_drives() -> list[dict]:
    out = [_drive(str(Path.home()), "Dieser Computer", "internal")]
    tran = {}
    try:
        data = json.loads(system.run(["lsblk", "-J", "-o", "NAME,MOUNTPOINT,TRAN,RM,TYPE"], 10).stdout)

        def walk(devs, t=None, rm=False):
            for d in devs:
                tt, rr = d.get("tran") or t, bool(d.get("rm")) or rm
                if d.get("mountpoint"):
                    tran[d["mountpoint"]] = ("removable" if rr else "external" if tt == "usb" else "nvme" if tt == "nvme" else "internal")
                walk(d.get("children") or [], tt, rr)
        walk(data.get("blockdevices", []))
    except Exception:  # noqa: BLE001
        pass
    seen = set()
    try:
        mounts = Path("/proc/mounts").read_text().splitlines()
    except OSError:
        mounts = []
    for line in mounts:
        parts = line.split()
        if len(parts) < 3:
            continue
        mp, fstype = parts[1].replace("\\040", " "), parts[2]
        if not mp.startswith(("/media/", "/run/media/", "/mnt/", "/srv/")) or mp in seen:
            continue
        seen.add(mp)
        kind = "network" if fstype in ("nfs", "nfs4", "cifs", "smb3", "smbfs", "fuse.sshfs") else tran.get(mp, "external")
        out.append(_drive(mp, Path(mp).name, kind))
    return [d for d in out if d]


def drives() -> list[dict]:
    try:
        found = _mac_drives() if sys.platform == "darwin" else _windows_drives() if sys.platform == "win32" else _linux_drives()
        return [d for d in found if d["kind"] == "internal" and d["path"] == str(Path.home()) or d["total_gb"] >= 1]  # no pseudo mounts
    except Exception:  # noqa: BLE001 - never block the choice: the home folder always works
        d = _drive(str(Path.home()), "Dieser Computer", "internal")
        return [d] if d else []


def suggest(drive_path: str) -> dict:
    """Folder names REKORD would use on a drive."""
    base = Path(drive_path)
    if base == Path.home():
        return {"home": str(config.DEFAULT_HOME), "models": str(config.DEFAULT_HOME / "models")}
    return {"home": str(base / "Rekord"), "models": str(base / "Rekord" / "models")}


def info() -> dict:
    s = config.load()
    return {
        "home": str(config.HOME), "home_default": str(config.DEFAULT_HOME), "home_missing": config.home_missing(),
        "home_free_gb": free_gb(config.HOME),
        "models": str(config.MODELS_DIR), "models_custom": bool(s.get("models_dir")), "models_missing": config.models_missing(),
        "models_free_gb": free_gb(config.MODELS_DIR), "ollama_models": str(ollama_dir()),
        "chosen": bool(s.get("storage_chosen")), "job": job(),
        "env_locked": bool(os.environ.get("REKORD_HOME")),  # set by the environment: can't be changed here
    }


def usage() -> dict:
    return {"data_gb": round(size_bytes(config.HOME) / 1e9, 2), "models_gb": round(size_bytes(config.MODELS_DIR) / 1e9, 2),
            "ollama_gb": round(size_bytes(ollama_dir()) / 1e9, 2) if ollama_dir().exists() else 0.0}


# ------------------------------------------------------------------ moving

def job() -> dict:
    with _lock:
        return dict(_job)


def _set(**kw) -> None:
    with _lock:
        _job.update(kw)


def _inside(a: Path, b: Path) -> bool:
    try:
        a.resolve().relative_to(b.resolve())
        return True
    except ValueError:
        return False


def _check_target(target: Path, need: int) -> None:
    root = target
    while not root.exists() and root != root.parent:
        root = root.parent
    if not os.access(root, os.W_OK):
        raise RuntimeError(f"Kein Schreibzugriff auf {root}")
    free = shutil.disk_usage(root).free
    if free < need * 1.05 + 200e6:
        raise RuntimeError(f"Zu wenig Platz: {free / 1e9:.1f} GB frei, gebraucht {need / 1e9:.1f} GB")


def _copy_tree(src: Path, dst: Path, skip: set[Path] = frozenset()) -> None:
    """Copy with progress (bytes) into the running job; keeps the source untouched."""
    for root, dirs, files in os.walk(src):
        rp = Path(root)
        dirs[:] = [d for d in dirs if (rp / d) not in skip]
        out = dst / rp.relative_to(src)
        out.mkdir(parents=True, exist_ok=True)
        for f in files:
            if f in ("rekord.db", "rekord.db-wal", "rekord.db-shm") and rp == src:
                continue  # the database is copied consistently with the SQLite backup API
            sp, dp = rp / f, out / f
            if sp.is_symlink():
                continue
            with open(sp, "rb") as a, open(dp, "wb") as b:
                while chunk := a.read(4 << 20):
                    b.write(chunk)
                    with _lock:
                        _job["done"] += len(chunk)
            shutil.copystat(sp, dp, follow_symlinks=False)


def _busy() -> str:
    from . import jobs, live
    if live.active():
        return "Es läuft gerade eine Aufnahme."
    if jobs.pending():
        return "REKORD verarbeitet gerade eine Aufnahme – kurz warten."
    return ""


def start(fn, what: str) -> dict:
    with _lock:
        if _job["state"] == "running":
            raise RuntimeError("Es wird schon verschoben.")
        _job.update(state="running", what=what, done=0, total=0, error="", restart=False)

    def run():
        try:
            fn()
            _set(state="done")
        except Exception as e:  # noqa: BLE001 - shown in the UI
            _set(state="error", error=str(e))
    threading.Thread(target=run, daemon=True, name="storage").start()
    return job()


def move_models(target: str, take_ollama: bool = True) -> dict:
    """Speech models (and the local AI models) into another folder/drive."""
    new = Path(target).expanduser()
    old = config.MODELS_DIR
    if why := _busy():
        raise RuntimeError(why)
    if new.resolve() == old.resolve():
        return job()
    old_ollama = ollama_dir()

    def work():
        from .engines import asr, voiceprint
        from .llm import ollama
        new_ollama = new / "ollama"
        ollama_src = old_ollama if take_ollama and old_ollama.exists() and not _inside(new_ollama, old_ollama) else None
        need = (size_bytes(old) if old.exists() else 0) + (size_bytes(ollama_src) if ollama_src else 0)
        _check_target(new, need)
        _set(total=need)
        if old.exists():
            _copy_tree(old, new, skip={old / "ollama"})
        if ollama_src:
            ollama.stop()
            _copy_tree(ollama_src, new_ollama)
        config.save({"models_dir": "" if new == config.HOME / "models" else str(new)})
        asr._sherpa.cache_clear()
        asr._faster.cache_clear()
        voiceprint.get_embedder.cache_clear()
        for src in ([old] if old.exists() and not _inside(new, old) else []) + ([ollama_src] if ollama_src else []):
            shutil.rmtree(src, ignore_errors=True)  # only after everything arrived
        ollama.apply_models_dir()
    return start(work, "Modelle")


def move_home(target: str) -> dict:
    """The whole data folder (recordings, database, voiceprints; models too unless they live elsewhere).
    Ends with a restart, because every part of REKORD has the old folder open."""
    new = Path(target).expanduser()
    old = config.HOME
    if os.environ.get("REKORD_HOME"):
        raise RuntimeError("Der Datenordner ist über REKORD_HOME fest eingestellt.")
    if why := _busy():
        raise RuntimeError(why)
    if new.resolve() == old.resolve():
        return job()
    if _inside(new, old):
        raise RuntimeError("Der neue Ort liegt im alten Datenordner – bitte einen anderen wählen.")
    if new.exists() and any(new.iterdir()):
        if not (new / "rekord.db").exists():
            raise RuntimeError(f"{new} ist nicht leer. Bitte einen leeren oder neuen Ordner wählen.")

    def work():
        from . import db
        models_inside = _inside(config.MODELS_DIR, old)
        need = size_bytes(old)
        _check_target(new, need)
        _set(total=need)
        new.mkdir(parents=True, exist_ok=True)
        _copy_tree(old, new)
        src = sqlite3.connect(config.DB_PATH)
        dst = sqlite3.connect(new / "rekord.db")
        with dst:
            src.backup(dst)
        src.close()
        # audio paths are stored absolute: point them to the new folder
        dst.execute("UPDATE recordings SET audio_path = ? || substr(audio_path, ?) WHERE audio_path LIKE ? || '%'",
                    (str(new), len(str(old)) + 1, str(old)))
        dst.commit()
        dst.close()
        s = json.loads((new / "settings.json").read_text("utf-8")) if (new / "settings.json").exists() else {}
        if models_inside and s.get("models_dir"):
            s["models_dir"] = str(new / Path(s["models_dir"]).relative_to(old))
        s["storage_chosen"] = True
        (new / "settings.json").write_text(json.dumps(s, indent=2, ensure_ascii=False), "utf-8")
        set_pointer(new)
        db.close()
        (old / "MOVED-TO.txt").write_text(f"REKORD-Daten sind umgezogen nach:\n{new}\n\nDieser Ordner kann gelöscht werden.\n", "utf-8")
        _set(restart=True)
        schedule_restart()
    return start(work, "Daten")


def set_pointer(home: Path) -> None:
    p = config.pointer_path()
    if Path(home).resolve() == config.DEFAULT_HOME.resolve():
        p.unlink(missing_ok=True)
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"home": str(home)}, ensure_ascii=False), "utf-8")


def forget_missing_home() -> None:
    """The external drive is gone for good: start fresh on the computer (the data on the drive stays untouched)."""
    config.pointer_path().unlink(missing_ok=True)
    schedule_restart()


# ------------------------------------------------------------------ restart

def schedule_restart(delay: float = 1.5) -> None:
    def go():
        time.sleep(delay)
        restart()
    threading.Thread(target=go, daemon=True).start()


def restart() -> None:
    """Start REKORD again with the same arguments (window or background), then end this process."""
    import subprocess
    env = dict(os.environ, REKORD_RESTARTING="1")
    args = sys.argv[1:] if system.frozen() else ["-m", "rekord", *sys.argv[1:]]
    if not system.frozen() and sys.argv and sys.argv[0].endswith("launch.py"):
        args = sys.argv
    subprocess.Popen([sys.executable, *args], env=env, **system.hidden())
    os._exit(0)
