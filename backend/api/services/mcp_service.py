import json
import uuid
from pathlib import Path

from sqlalchemy import select

from db import commit
from models.agent import Agent
from models.mcp import AgentMcpPermission
from runtime.mcp_config import McpServerRef

_POOL_CACHE: dict[tuple[Path, ...], tuple[tuple[float, ...], list[McpServerRef]]] = {}


def default_pool_paths(repo_root: Path) -> list[Path]:
    return [Path.home() / ".claude.json", repo_root / ".mcp.json"]


def read_mcp_pool(paths: list[Path]) -> list[McpServerRef]:
    """Read-only (README 16): the terminal owns server definitions. Cached and refreshed only when a file's mtime changes, per 16's "cache and refresh on demand"."""
    key = tuple(paths)
    mtimes = tuple(path_mtime(path) for path in paths)
    cached = _POOL_CACHE.get(key)
    if cached is not None and cached[0] == mtimes:
        return cached[1]
    servers = parse_pool(paths)
    _POOL_CACHE[key] = (mtimes, servers)
    return servers


def path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def parse_pool(paths: list[Path]) -> list[McpServerRef]:
    servers: dict[str, McpServerRef] = {}
    for path in paths:
        servers.update(read_pool_file(path))
    return list(servers.values())


def read_pool_file(path: Path) -> dict[str, McpServerRef]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {name: build_server_ref(name, connection) for name, connection in data.get("mcpServers", {}).items()}


def build_server_ref(name: str, connection: dict) -> McpServerRef:
    transport = connection.get("type") or ("stdio" if "command" in connection else "http")
    return McpServerRef(name=name, transport=transport, connection=connection)


async def grant_mcp_access(db, agent: Agent, server_name: str) -> AgentMcpPermission:
    permission = await find_permission(db, agent.id, server_name)
    if permission is None:
        permission = AgentMcpPermission(id=uuid.uuid4(), agent_id=agent.id, mcp_server_name=server_name)
        db.add(permission)
    permission.allowed = True
    await commit(db)
    return permission


async def revoke_mcp_access(db, agent: Agent, server_name: str) -> None:
    permission = await find_permission(db, agent.id, server_name)
    if permission is not None:
        permission.allowed = False
        await commit(db)


async def find_permission(db, agent_id: uuid.UUID, server_name: str) -> AgentMcpPermission | None:
    query = select(AgentMcpPermission).where(AgentMcpPermission.agent_id == agent_id, AgentMcpPermission.mcp_server_name == server_name)
    return (await db.execute(query)).scalars().first()


async def resolve_allowed_servers(db, agent_id: uuid.UUID, pool: list[McpServerRef]) -> list[McpServerRef]:
    """A stored permission for a server the terminal no longer has is silently dropped, never a spawn failure (README 16)."""
    permissions = await list_agent_permissions(db, agent_id)
    allowed_names = {permission.mcp_server_name for permission in permissions}
    return [server for server in pool if server.name in allowed_names]


async def list_agent_permissions(db, agent_id: uuid.UUID) -> list[AgentMcpPermission]:
    query = select(AgentMcpPermission).where(AgentMcpPermission.agent_id == agent_id, AgentMcpPermission.allowed.is_(True))
    return list((await db.execute(query)).scalars())
