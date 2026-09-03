import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class McpServerRef:
    name: str
    transport: str
    connection: dict


def write_mcp_config(runtime_dir: Path, allowed_servers: list[McpServerRef]) -> Path:
    """Write the allow-list only. Never a credential: those live in the terminal config."""
    runtime_dir.mkdir(parents=True, exist_ok=True)
    config_path = runtime_dir / "mcp.json"
    servers = {server.name: server.connection for server in allowed_servers}
    config_path.write_text(json.dumps({"mcpServers": servers}, indent=2))
    return config_path
