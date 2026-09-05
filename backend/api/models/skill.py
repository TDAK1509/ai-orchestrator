import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class SkillSource(str, enum.Enum):
    IMPORTED = "imported"
    CUSTOM = "custom"


class Skill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A queryable index of the Skill Catalog (README 15): an IMPORTED row is pulled from Claude Code's own skill directory and may be overwritten by the next import, a CUSTOM row is authored in the UI and owns its own instructions."""

    __tablename__ = "skills"

    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    repository_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[SkillSource] = mapped_column(
        Enum(SkillSource, native_enum=False, length=10), default=SkillSource.CUSTOM, server_default=text("'CUSTOM'"), nullable=False
    )
    instructions: Mapped[str | None] = mapped_column(String, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class AgentSkillAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_skill_assignments"
    __table_args__ = (UniqueConstraint("agent_id", "skill_id"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=False)
    skill_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("skills.id"), nullable=False, index=True)
