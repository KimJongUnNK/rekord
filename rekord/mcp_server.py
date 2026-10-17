"""MCP server: plug your REKORD library into Claude Desktop / Claude Code (or any MCP client).

Claude then reads your transcripts directly - works with a normal Claude subscription, no API key needed.
Config (claude_desktop_config.json):
    {"mcpServers": {"rekord": {"command": "<python>", "args": ["-m", "rekord", "mcp"]}}}
"""
from __future__ import annotations

import datetime as dt

try:  # MCP Python SDK 2.x
    from mcp.server.mcpserver import MCPServer
except ImportError:  # 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer

from . import db, export
from .summarize import fmt_time

mcp = MCPServer("rekord",
                instructions="REKORD: the user's locally recorded meetings - transcripts with speaker names, summaries, voice-recognized people.")


@mcp.tool()
def list_recordings(query: str = "", limit: int = 30) -> list[dict]:
    """List recordings (newest first). Optional full-text query over titles and transcripts."""
    return [{"id": r["id"], "title": r["title"], "date": dt.datetime.fromtimestamp(r["created_at"]).isoformat(timespec="minutes"),
             "duration": fmt_time(r["duration"] or 0), "speakers": [x["name"] for x in r["speakers"]], "status": r["status"]}
            for r in db.list_recordings(q=query)[:limit]]


@mcp.tool()
def get_transcript(recording_id: str) -> str:
    """Full transcript with speaker names and timestamps, plus existing summaries, as Markdown."""
    if not db.get_recording(recording_id):
        return f"Recording {recording_id} not found"
    return export.markdown(recording_id)


@mcp.tool()
def search_transcripts(query: str, limit: int = 25) -> list[dict]:
    """Full-text search across all transcripts. Returns matching lines with recording, speaker and time."""
    return [{"recording_id": h["recording_id"], "recording": h["recording_title"], "speaker": h["speaker"],
             "time": fmt_time(h["start"]), "text": h["text"]} for h in db.search_segments(query, limit=limit)]


@mcp.tool()
def list_people() -> list[dict]:
    """Known people (voice profiles) and in how many recordings they appear."""
    return [{"name": p["name"], "recordings": p["recordings"]} for p in db.list_profiles()]


@mcp.tool()
def save_summary(recording_id: str, title: str, markdown: str) -> str:
    """Store a summary you wrote for a recording, so it shows up in the REKORD app."""
    if not db.get_recording(recording_id):
        return "not found"
    db.add_summary(recording_id, "mcp", title, markdown, "mcp", "claude")
    return "saved"


def run() -> None:
    mcp.run()
