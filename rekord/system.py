"""Small OS helpers shared by the one-click features: child processes, RAM, firewall, shortcuts, autostart."""
from __future__ import annotations

import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

PORTS = (8765, 8766)  # http (desktop, iPhone app) + https (phone browser)


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def ensure_output() -> Path | None:
    """A windowed app started by double-click (Windows) has no console: sys.stdout/sys.stderr are None, and the
    web server crashes when it sets up its log output. Then everything goes into a log file next to the
    settings (…/REKORD/rekord.log) – which also helps when something needs explaining. Returns that file."""
    if sys.stdout is not None and sys.stderr is not None:
        return None
    from . import config
    path = config.pointer_path().parent / "rekord.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 5 * 2**20:  # keep it small: start over at 5 MB
            path.replace(path.with_suffix(".old.log"))
        out = open(path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - lives as long as the app
    except OSError:
        path, out = None, open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    sys.stdout = sys.stdout or out
    sys.stderr = sys.stderr or out
    return path


def child_env() -> dict:
    """Environment for programs we start (xdg-open, pkexec, ollama, claude …). The packaged Linux app puts
    its own libraries on LD_LIBRARY_PATH; system programs must get the original value back."""
    env = dict(os.environ)
    if "LD_LIBRARY_PATH_ORIG" in env:
        env["LD_LIBRARY_PATH"] = env.pop("LD_LIBRARY_PATH_ORIG")
    elif frozen() and sys.platform.startswith("linux"):
        env.pop("LD_LIBRARY_PATH", None)
    return env


def hidden() -> dict:
    """Popen kwargs: no console window on Windows, detached from our process group elsewhere."""
    if sys.platform == "win32":
        return {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    return {"start_new_session": True}


def ram_gb() -> float:
    try:
        if sys.platform == "win32":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MemoryStatus()
            m.dwLength = ctypes.sizeof(MemoryStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return round(m.ullTotalPhys / 2**30, 1)
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    except (OSError, ValueError, AttributeError):
        return 8.0


def app_command() -> list[str]:
    """How to start this REKORD again (packaged app or source install)."""
    return [sys.executable] if frozen() else [sys.executable, "-m", "rekord"]


# ------------------------------------------------------------------ Linux firewall (iPhone needs the ports)

def run(cmd: list[str], timeout: float = 30) -> subprocess.CompletedProcess:
    """subprocess.run that can't hang: on timeout the whole process group is killed (a grandchild holding
    our pipes would otherwise block forever), stdin is closed, no console window on Windows."""
    kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True,
                "env": child_env()}
    if sys.platform == "win32":
        kw["creationflags"] = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen(cmd, **kw)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, creationflags=0x08000000)
        else:
            import signal
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
        try:
            out, err = p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        raise subprocess.TimeoutExpired(cmd, timeout, out, err) from None
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)


def _run(cmd: list[str], timeout: float = 10) -> subprocess.CompletedProcess | None:
    try:
        return run(cmd, timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def firewall() -> dict:
    """Which Linux firewall blocks the iPhone, and are our ports open? (other systems ask on their own)"""
    out = {"tool": None, "open": None, "can_fix": bool(shutil.which("pkexec"))}
    if not sys.platform.startswith("linux"):
        return out
    if shutil.which("firewall-cmd"):
        r = _run(["firewall-cmd", "--state"])
        if r and r.returncode == 0 and "running" in r.stdout:
            out["tool"] = "firewalld"
            q = [_run(["firewall-cmd", f"--query-port={p}/tcp"]) for p in PORTS]
            if all(x and x.returncode in (0, 1) for x in q):
                out["open"] = all(x.returncode == 0 for x in q) or _zone_allows_high_ports()
            return out
    conf = Path("/etc/ufw/ufw.conf")
    if shutil.which("ufw") and conf.exists() and "ENABLED=yes" in conf.read_text(errors="ignore"):
        out["tool"] = "ufw"  # rules are only readable as root
    return out


def _zone_allows_high_ports() -> bool:
    r = _run(["firewall-cmd", "--list-ports"])
    return bool(r and "1025-65535/tcp" in r.stdout)  # Fedora Workstation's default zone


def open_firewall() -> dict:
    """Open the REKORD ports. pkexec shows the normal system password dialog."""
    fw = firewall()
    if not fw["tool"]:
        return {"ok": True, "message": "Keine aktive Firewall – nichts zu tun."}
    if not fw["can_fix"]:
        raise RuntimeError("pkexec fehlt – bitte die Befehle aus der Anleitung im Terminal ausführen.")
    if fw["tool"] == "firewalld":
        ports = " ".join(f"--add-port={p}/tcp" for p in PORTS)
        script = f"firewall-cmd --permanent {ports} --add-service=mdns && firewall-cmd --reload"
    else:
        script = " && ".join(f"ufw allow {p}/tcp" for p in PORTS) + " && ufw allow 5353/udp"
    r = _run(["pkexec", "/bin/sh", "-c", script], timeout=180)
    if r is None or r.returncode != 0:
        raise RuntimeError("Abgebrochen oder kein Passwort eingegeben." if r is not None and r.returncode in (126, 127)
                           else f"Firewall-Änderung fehlgeschlagen: {(r.stderr or r.stdout).strip() if r else 'pkexec nicht startbar'}")
    return {"ok": True, "message": "Freigegeben – das iPhone kann sich jetzt verbinden."}


# ------------------------------------------------------------------ Windows: Start menu entry for the zip version

def _powershell(script: str) -> bool:
    r = _run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], timeout=30)
    return bool(r and r.returncode == 0)


def _shortcut(lnk: Path, target: str, args: str = "") -> bool:
    lnk.parent.mkdir(parents=True, exist_ok=True)
    ps = lambda s: "'" + s.replace("'", "''") + "'"  # noqa: E731 - PowerShell single-quote escaping
    return _powershell(f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({ps(str(lnk))});"
                       f"$s.TargetPath={ps(target)};$s.Arguments={ps(args)};"
                       f"$s.WorkingDirectory={ps(str(Path(target).parent))};$s.IconLocation={ps(target + ',0')};$s.Save()")


def ensure_start_menu() -> None:
    """Packaged Windows app: keep a Start menu entry pointing at wherever REKORD.exe lives now."""
    if sys.platform != "win32" or not frozen():
        return
    from . import config
    lnk = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/REKORD.lnk"
    stamp = config.HOME / ".startmenu"
    try:
        if lnk.exists() and stamp.exists() and stamp.read_text("utf-8") == sys.executable:
            return
        if _shortcut(lnk, sys.executable):
            stamp.write_text(sys.executable, "utf-8")
    except OSError:
        pass


# ------------------------------------------------------------------ other REKORD processes (updates: never two versions)

_EXE = re.compile(r'(?:^|[/\\])REKORD(?:\.exe)?"?(?=\s|$)', re.I)  # the packaged app's executable, end of its path
CLI = {"mcp", "serve", "process", "models", "enroll", "desktop"}  # CLI uses (e.g. Claude Desktop's MCP server) stay


def rekord_processes() -> list[tuple[int, str]]:
    """Other running REKORD apps (packaged): [(pid, first argument)], this process excluded. Only processes whose
    program IS REKORD count – not e.g. a terminal command that merely mentions a REKORD path."""
    me = {os.getpid(), os.getppid()}
    rows: list[tuple[str, str]] = []
    try:
        if sys.platform == "win32":
            r = run(["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_Process -Filter \"Name='REKORD.exe'\" | "
                     "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"], timeout=30)
            rows = [tuple((ln.split("\t", 1) + [""])[:2]) for ln in r.stdout.splitlines() if ln.strip()]
        else:
            # program name first (Linux: "REKORD", macOS: the full path …/MacOS/REKORD), then its arguments
            r = run(["ps", "-axo", "pid=,comm="], timeout=15)
            pids = [ln.split(None, 1)[0] for ln in r.stdout.splitlines()
                    if len(ln.split(None, 1)) == 2 and re.split(r"[/\\]", ln.split(None, 1)[1].strip())[-1] == "REKORD"]
            for pid in pids:
                a = run(["ps", "-o", "args=", "-p", pid], timeout=15).stdout.strip()
                if a:
                    rows.append((pid, a))
    except Exception:  # noqa: BLE001
        return []
    out = []
    for pid, cmd in rows:
        m = ([None] + list(_EXE.finditer(cmd)))[-1]  # the last one: folders like "REKORD 2.app" come before it
        if not pid.strip().isdigit() or int(pid) in me:
            continue
        rest = cmd[m.end():].split() if m else []
        out.append((int(pid), rest[0].strip('"') if rest else ""))
    return out


def stop_other_instances() -> list[int]:
    """End other REKORD app processes (e.g. the window of an older version). CLI uses like `REKORD mcp` stay.
    Only the installed app does this – never a source checkout or the tests."""
    stopped: list[int] = []
    if not frozen():
        return stopped
    for pid, first in rekord_processes():
        if first in CLI:
            continue
        try:
            if sys.platform == "win32":
                run(["taskkill", "/PID", str(pid), "/F"], timeout=15)
            else:
                import signal
                os.kill(pid, signal.SIGTERM)
            stopped.append(pid)
        except OSError:
            pass
    return stopped


# ------------------------------------------------------------------ start with the computer (hub in the background)

LAUNCH_AGENT = Path.home() / "Library/LaunchAgents/app.rekord.hub.plist"
LINUX_AUTOSTART = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart/rekord.desktop"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_supported() -> tuple[bool, str]:
    if not frozen():
        return False, "Nur in der installierten App verfügbar."
    if sys.platform == "darwin" and "/AppTranslocation/" in sys.executable:
        return False, "Zuerst REKORD in den Ordner Programme ziehen."
    return True, ""


def autostart_enabled() -> bool:
    if sys.platform == "darwin":
        return LAUNCH_AGENT.exists()
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
                winreg.QueryValueEx(k, "REKORD")
            return True
        except OSError:
            return False
    return LINUX_AUTOSTART.exists()


def set_autostart(on: bool) -> bool:
    ok, why = autostart_supported()
    if on and not ok:
        raise RuntimeError(why)
    cmd = app_command() + ["--background"]
    if sys.platform == "darwin":
        if on:
            LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)
            LAUNCH_AGENT.write_bytes(plistlib.dumps({
                "Label": "app.rekord.hub", "ProgramArguments": cmd, "RunAtLoad": True,
                "ProcessType": "Interactive", "StandardOutPath": "/dev/null", "StandardErrorPath": "/dev/null"}))
        else:
            LAUNCH_AGENT.unlink(missing_ok=True)
    elif sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, "REKORD", 0, winreg.REG_SZ, subprocess.list2cmdline(cmd))
            else:
                try:
                    winreg.DeleteValue(k, "REKORD")
                except FileNotFoundError:
                    pass
    else:
        if on:
            LINUX_AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
            exe = os.environ.get("APPIMAGE") or " ".join(f'"{c}"' for c in app_command())
            if os.environ.get("APPIMAGE"):
                exe = f'"{exe}"'
            LINUX_AUTOSTART.write_text("[Desktop Entry]\nType=Application\nName=REKORD (Hintergrund)\n"
                                       f"Exec={exe} --background\nIcon=rekord\nTerminal=false\n"
                                       "X-GNOME-Autostart-enabled=true\nNoDisplay=true\n", "utf-8")
        else:
            LINUX_AUTOSTART.unlink(missing_ok=True)
    return autostart_enabled()
