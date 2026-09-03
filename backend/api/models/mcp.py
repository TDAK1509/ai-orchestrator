import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentMcpPermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The only application state for MCP (README 16): server definitions themselves live in the terminal config, never here."""

    __tablename__ = "agent_mcp_permissions"
    __table_args__ = (UniqueConstraint("agent_id", "mcp_server_name"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=False)
    mcp_server_name: Mapped[str] = mapped_column(String(120), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
