"""One click instead of copy & paste: register REKORD as MCP server in Claude Desktop and Claude Code."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import config, system


def mcp_entry() -> dict:
    cmd = system.app_command() + ["mcp"]
    return {"command": cmd[0], "args": cmd[1:], "env": {"REKORD_HOME": str(config.HOME)}}


# ------------------------------------------------------------------ Claude Desktop

def _desktop_dirs() -> list[Path]:
    home = Path.home()
    if sys.platform == "darwin":
        return [home / "Library/Application Support/Claude"]
    if sys.platform == "win32":
        dirs = [Path(os.environ.get("APPDATA", home / "AppData/Roaming")) / "Claude"]
        pkgs = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local")) / "Packages"
        dirs += sorted(pkgs.glob("Claude_*/LocalCache/Roaming/Claude")) if pkgs.exists() else []  # Microsoft Store version
        return dirs
    return [Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "Claude"]


def _desktop_app() -> str | None:
    if sys.platform == "darwin":
        return next((a for a in ("/Applications/Claude.app", str(Path.home() / "Applications/Claude.app")) if Path(a).exists()), None)
    if sys.platform == "win32":
        exe = Path(os.environ.get("LOCALAPPDATA", "")) / "AnthropicClaude/claude.exe"
        return str(exe) if exe.exists() else None
    return shutil.which("claude-desktop")


def _read(path: Path) -> dict:
    if not path.exists() or not path.read_text("utf-8").strip():
        return {}
    data = json.loads(path.read_text("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("unerwartetes Format")
    return data


def claude_desktop() -> dict:
    dirs = [d for d in _desktop_dirs() if d.exists()]
    connected = False
    for d in dirs:
        try:
            connected |= "rekord" in _read(d / "claude_desktop_config.json").get("mcpServers", {})
        except (ValueError, OSError):
            pass
    app = _desktop_app()
    return {"installed": bool(dirs or app), "connected": connected, "running": _desktop_running(),
            "path": str((dirs or _desktop_dirs())[0] / "claude_desktop_config.json"), "download_url": "https://claude.ai/download"}


def connect_claude_desktop() -> dict:
    """Merge our server into claude_desktop_config.json (other servers and settings stay untouched)."""
    dirs = [d for d in _desktop_dirs() if d.exists()] or _desktop_dirs()[:1]
    written = []
    for d in dirs:
        path = d / "claude_desktop_config.json"
        try:
            data = _read(path)
        except ValueError as e:
            raise RuntimeError(f"{path} ist kein gültiges JSON – bitte in Claude Desktop prüfen ({e}).") from e
        d.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.copy2(path, path.with_suffix(".json.bak"))
        data.setdefault("mcpServers", {})["rekord"] = mcp_entry()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        os.replace(tmp, path)
        written.append(str(path))
    return {"ok": True, "paths": written, "running": _desktop_running()}


def _desktop_running() -> bool:
    try:
        if sys.platform == "darwin":
            return system.run(["pgrep", "-x", "Claude"], 10).returncode == 0
        if sys.platform == "win32":
            return "claude.exe" in system.run(["tasklist", "/FI", "IMAGENAME eq claude.exe", "/NH"], 15).stdout.lower()
    except (OSError, subprocess.SubprocessError):
        pass
    return False


def restart_claude_desktop() -> bool:
    """Claude Desktop reads its MCP config only at start."""
    env = system.child_env()
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", 'tell application "Claude" to quit'], capture_output=True, env=env)
        for _ in range(20):
            if not _desktop_running():
                break
            time.sleep(0.5)
        return subprocess.run(["open", "-a", "Claude"], capture_output=True, env=env).returncode == 0
    if sys.platform == "win32":
        app = _desktop_app()
        subprocess.run(["taskkill", "/IM", "claude.exe"], capture_output=True, **system.hidden())
        for _ in range(20):
            if not _desktop_running():
                break
            time.sleep(0.5)
        if app:
            subprocess.Popen([app], env=env, **system.hidden())
            return True
    return False


# ------------------------------------------------------------------ Claude Code (CLI)

def _claude_cli() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    for p in (Path.home() / ".local/bin/claude", Path.home() / ".claude/local/claude",
              Path.home() / ".local/bin/claude.exe", Path("/opt/homebrew/bin/claude"), Path("/usr/local/bin/claude")):
        if p.exists():
            return str(p)
    return None


def _cli(*args: str, timeout: float = 30) -> subprocess.CompletedProcess:
    exe = _claude_cli()
    if not exe:
        raise RuntimeError("Claude Code ist nicht installiert.")
    cmd = [exe, *args]
    if sys.platform == "win32" and exe.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c", *cmd]
    return system.run(cmd, timeout)


def claude_code() -> dict:
    exe = _claude_cli()
    connected = False
    if exe:
        try:
            connected = _cli("mcp", "get", "rekord", timeout=15).returncode == 0
        except (OSError, subprocess.SubprocessError):
            pass
    return {"installed": bool(exe), "connected": connected}


def connect_claude_code() -> dict:
    entry = {"type": "stdio", **mcp_entry()}
    _cli("mcp", "remove", "--scope", "user", "rekord")  # re-add = update (e.g. after REKORD moved)
    r = _cli("mcp", "add-json", "--scope", "user", "rekord", json.dumps(entry))
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or "claude mcp add-json fehlgeschlagen")
    return {"ok": True}
