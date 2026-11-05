"""Run an isolated localhost server and exercise it with the official MCP client.

Run from the repository root: uv run python -m scripts.smoke_agents
This uses a temporary database, an ephemeral port and synthetic data. It never
contacts xAI, KSeF or the deployed application and never resets an existing DB.
"""

import asyncio
import json
import os
import secrets
import socket
import tempfile
import threading
import time

import httpx
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from main import create_app


def tool_data(result) -> dict:
    assert not result.isError, "MCP tool returned an error"
    return result.structuredContent or json.loads(result.content[0].text)


async def exercise(url: str, key: str) -> None:
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {key}"}, timeout=30, trust_env=False) as http:
        synced = await http.post(f"{url}/api/ksef/sync")
        synced.raise_for_status()
        run = await http.post(f"{url}/api/agents/run", json={"mode": "demo"})
        run.raise_for_status()
        assert [r["status"] for r in run.json()] == ["completed", "completed", "waiting_for_client"]
        async with streamable_http_client(f"{url}/mcp", http_client=http) as (receive, send, _):
            async with ClientSession(receive, send) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) == 6
                status = tool_data(await session.call_tool("get_status", {}))
                question = status["open_questions"][0]
                reply = {"question_id": question["id"], "answer": {
                    "vehicle_plate": "GD 9R247", "usage": "mixed", "business_purpose": "Travel to a client site",
                }}
                resolved = tool_data(await session.call_tool("answer_question", reply))
                replayed = tool_data(await session.call_tool("answer_question", reply))
                assert resolved["status"] == replayed["status"] == "completed"
                assert len(replayed["invoice"]["postings"]) == 1
                assert replayed["invoice"]["postings"][0]["deductible_vat"] == "23.00"
                assert replayed["questions"][0]["status"] == "resolved"
                print(json.dumps({"mcp_tools": len(tools.tools), "initial_states": [r["status"] for r in run.json()],
                                  "resolved_state": replayed["status"], "duplicate_postings": 0, "simulation": True}))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="grok-agent-smoke-") as directory:
        os.environ["DATA_DIR"] = directory
        os.environ["PLATFORM_API_KEY"] = key = secrets.token_urlsafe(24)
        os.environ["AGENT_MODE"] = "demo"
        os.environ.pop("MCP_INVITE_TOKEN", None)
        os.environ.pop("RELEASE", None)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(create_app(), log_level="error", access_log=False))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + 45
                while not server.started and thread.is_alive() and time.monotonic() < deadline:
                    time.sleep(0.05)
                if not server.started:
                    raise RuntimeError("Isolated smoke server failed to start")
                asyncio.run(exercise(f"http://127.0.0.1:{port}", key))
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                if thread.is_alive():
                    raise RuntimeError("Smoke server did not stop")


if __name__ == "__main__":
    main()
