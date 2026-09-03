import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorktreeStatus(str, enum.Enum):
    ACTIVE = "active"
    REMOVED = "removed"


class TaskWorktree(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One worktree per task. Survives the agent that started it."""

    __tablename__ = "task_worktrees"

    task_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("tasks.id"), nullable=False, unique=True
    )
    branch: Mapped[str] = mapped_column(String(200), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(200), nullable=False, default="main")
    path: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[WorktreeStatus] = mapped_column(
        Enum(WorktreeStatus, native_enum=False, length=10),
        default=WorktreeStatus.ACTIVE,
        nullable=False,
    )
