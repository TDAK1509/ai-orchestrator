import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Skill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A reference into the repository-backed Skill Catalog (README 15): git is the source of truth, this row is a queryable index of it."""

    __tablename__ = "skills"

    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    repository_path: Mapped[str] = mapped_column(String(500), nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class AgentSkillAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_skill_assignments"
    __table_args__ = (UniqueConstraint("agent_id", "skill_id"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=False)
    skill_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("skills.id"), nullable=False)
