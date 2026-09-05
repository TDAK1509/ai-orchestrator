#!/usr/bin/env python3
"""The internal MCP tool from PR 5: lets an agent file a new task, tagged with which agent created it -- visibility for a planner that splits its own work up, not a limit on it."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from internal_mcp_http import backend_api_base_url, backend_auth_headers
from mcp.server.mcpserver import MCPServer

server = MCPServer(name="agent-office-create-task")


@server.tool()
async def create_task(title: str, description: str | None = None, priority: str = "medium", repository_id: str | None = None) -> str:
    """Defaults to this run's own repository when none is given, so a planner splitting up its current task doesn't need to know the repository's id."""
    body = await build_create_task_body(title, description, priority, repository_id)
    async with httpx.AsyncClient(base_url=backend_api_base_url(), headers=backend_auth_headers()) as client:
        response = await client.post("/tasks", json=body)
        response.raise_for_status()
        return f"Created task {response.json()['id']}: {title}"


async def build_create_task_body(title: str, description: str | None, priority: str, repository_id: str | None) -> dict:
    return {
        "title": title,
        "description": description,
        "priority": priority,
        "repository_id": repository_id or await resolve_current_repository_id(),
        "created_by_agent_id": os.environ["AGENT_ID"],
    }


async def resolve_current_repository_id() -> str:
    task_id = os.environ.get("TASK_ID")
    if not task_id:
        raise RuntimeError("repository_id is required: this run has no task of its own to inherit a repository from")
    async with httpx.AsyncClient(base_url=backend_api_base_url(), headers=backend_auth_headers()) as client:
        response = await client.get(f"/tasks/{task_id}")
        response.raise_for_status()
        return response.json()["repository_id"]


if __name__ == "__main__":
    server.run(transport="stdio")
