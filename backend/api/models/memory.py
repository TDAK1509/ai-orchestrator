import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class MemoryScope(str, enum.Enum):
    WORKSPACE = "workspace"
    AGENT = "agent"
    TASK = "task"


class MemoryType(str, enum.Enum):
    FACT = "fact"
    DECISION = "decision"
    PREFERENCE = "preference"
    LESSON = "lesson"
    TASK_SUMMARY = "task_summary"
    PROJECT_CONTEXT = "project_context"
    CONVENTION = "convention"
    ARCHITECTURE = "architecture"


class MemoryStatus(str, enum.Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class MemorySourceType(str, enum.Enum):
    HUMAN = "human"
    AGENT = "agent"
    MEETING = "meeting"
    TASK = "task"
    SYSTEM = "system"


class MemoryRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Workspace and private memory are the same table with a different scope (README 32.1): one retrieval query, one editor, one backup."""

    __tablename__ = "memory_records"
    __table_args__ = (
        Index("ix_memory_records_agent_scope", "agent_id", "scope", "status"),
        Index("ix_memory_records_task_scope", "task_id", "scope", "status"),
        Index("ix_memory_records_scope_status", "scope", "status"),
        CheckConstraint(
            "(scope != 'workspace' OR agent_id IS NULL) "
            "AND (scope != 'agent' OR agent_id IS NOT NULL) "
            "AND (scope != 'task' OR task_id IS NOT NULL)",
            name="ck_memory_records_scope_owner",
        ),
    )

    scope: Mapped[MemoryScope] = mapped_column(Enum(MemoryScope, native_enum=False, length=10), nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("tasks.id"), nullable=True)

    type: Mapped[MemoryType] = mapped_column(Enum(MemoryType, native_enum=False, length=20), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)

    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    status: Mapped[MemoryStatus] = mapped_column(
        Enum(MemoryStatus, native_enum=False, length=10), default=MemoryStatus.ACTIVE, nullable=False
    )
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("memory_records.id"), nullable=True)

    source_type: Mapped[MemorySourceType | None] = mapped_column(
        Enum(MemorySourceType, native_enum=False, length=10), nullable=True
    )
    source_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # allow-comment: A2.1 -- a portable JSON float array, not a pgvector column, so the aiosqlite dev path keeps working; embedding_model lets a sweep re-embed rows left behind by a retired model instead of silently mixing incomparable vectors.
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MemoryProposalStatus(str, enum.Enum):
    PENDING = "pending"
    APPLIED = "applied"
    DISMISSED = "dismissed"


class MemoryProposal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A3.1: proposes a supersession, never applies it -- a wrong supersession silently deletes knowledge (README 32.4), so a human clicks."""

    __tablename__ = "memory_proposals"

    old_memory_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("memory_records.id"), nullable=False)
    new_memory_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("memory_records.id"), nullable=False)
    similarity: Mapped[float] = mapped_column(Float, nullable=False)

    status: Mapped[MemoryProposalStatus] = mapped_column(
        Enum(MemoryProposalStatus, native_enum=False, length=10), default=MemoryProposalStatus.PENDING, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
