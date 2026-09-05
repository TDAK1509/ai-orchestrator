"""Shared by every internal MCP subprocess that calls back into this backend's own HTTP API (PR 1, PR 5): the port and bearer token RuntimeService._build_internal_servers injects into the subprocess's own env, never the agent process's."""
import os


def backend_api_base_url() -> str:
    port = os.environ.get("AGENT_OFFICE_API_PORT", "8000")
    return f"http://localhost:{port}"


def backend_auth_headers() -> dict[str, str]:
    token = os.environ.get("AGENT_OFFICE_API_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}
