import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class McpServerRef:
    name: str
    transport: str
    connection: dict


def write_mcp_config(runtime_dir: Path, allowed_servers: list[McpServerRef], internal_servers: dict[str, dict] | None = None) -> Path:
    """Write the allow-list plus our own internal servers such as ask_human, never a third-party credential: those live in the terminal config."""
    runtime_dir.mkdir(parents=True, exist_ok=True)
    config_path = runtime_dir / "mcp.json"
    servers = {server.name: server.connection for server in allowed_servers}
    servers.update(internal_servers or {})
    config_path.write_text(json.dumps({"mcpServers": servers}, indent=2))
    os.chmod(config_path, 0o600)
    return config_path
