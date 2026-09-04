import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db, get_repo_root
from events.bus import bus
from events.schema import MCP_GRANTED, MCP_REVOKED
from lookups import get_or_404
from models.agent import Agent
from runtime.mcp_config import McpServerRef
from serialization import serialize
from services.mcp_service import (
    default_pool_paths,
    grant_mcp_access,
    list_agent_permissions,
    read_mcp_pool,
    revoke_mcp_access,
)

router = APIRouter(prefix="/mcp", tags=["mcp"])


class GrantMcpBody(BaseModel):
    server_name: str


@router.get("/pool")
async def list_pool_route(repo_root=Depends(get_repo_root)):
    pool = read_mcp_pool(default_pool_paths(repo_root))
    return [serialize_server_ref(server) for server in pool]


def serialize_server_ref(server: McpServerRef) -> dict:
    """Never the raw connection dict (README 16): it can carry the terminal's own credentials, which the app must never hold or expose."""
    return {"name": server.name, "transport": server.transport}


@router.get("/agents/{agent_id}")
async def list_agent_permissions_route(agent_id: uuid.UUID, db=Depends(get_db)):
    permissions = await list_agent_permissions(db, agent_id)
    return [serialize(permission) for permission in permissions]


@router.post("/agents/{agent_id}/grant", status_code=201)
async def grant_mcp_access_route(agent_id: uuid.UUID, body: GrantMcpBody, db=Depends(get_db)):
    agent = await get_or_404(db, Agent, agent_id, "agent")
    permission = await grant_mcp_access(db, agent, body.server_name)
    bus.publish(MCP_GRANTED, serialize(permission))
    return serialize(permission)


@router.delete("/agents/{agent_id}/revoke/{server_name}")
async def revoke_mcp_access_route(agent_id: uuid.UUID, server_name: str, db=Depends(get_db)):
    agent = await get_or_404(db, Agent, agent_id, "agent")
    await revoke_mcp_access(db, agent, server_name)
    bus.publish(MCP_REVOKED, {"agentId": str(agent_id), "serverName": server_name})
    return {"revoked": True}
