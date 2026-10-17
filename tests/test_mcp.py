"""MCP server: real stdio handshake with the official client (what Claude Desktop does)."""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from rekord import db

mcp = pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_mcp_tools_over_stdio(home):
    r = db.create_recording("MCP Meeting", "/nope.wav", duration=10)
    db.replace_transcript(r["id"], [{"label": 0, "name": "Lisa", "color": "#2D7FF9", "embedding": None}],
                          [{"start": 0, "end": 5, "label": 0, "text": "Die Getränkelizenz muss zum Amt."}])

    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "rekord", "mcp"], cwd=str(ROOT),
                                       env={**os.environ, "REKORD_HOME": str(home)})
        async with stdio_client(params) as (rd, wr):
            async with ClientSession(rd, wr) as s:
                await s.initialize()
                names = {t.name for t in (await s.list_tools()).tools}
                hits = await s.call_tool("search_transcripts", {"query": "Getränkelizenz"})
                transcript = await s.call_tool("get_transcript", {"recording_id": r["id"]})
                saved = await s.call_tool("save_summary", {"recording_id": r["id"], "title": "Von Claude", "markdown": "# ok"})
                return names, hits, transcript, saved

    names, hits, transcript, saved = asyncio.run(asyncio.wait_for(run(), 60))
    assert {"list_recordings", "get_transcript", "search_transcripts", "list_people", "save_summary"} <= names
    hit = json.loads(hits.content[0].text)
    assert hit["speaker"] == "Lisa" and hit["recording_id"] == r["id"]
    assert "**Lisa** [00:00]" in transcript.content[0].text
    assert saved.content[0].text == "saved"
    assert db.list_summaries(r["id"])[0]["title"] == "Von Claude"
    db.delete_recording(r["id"])
