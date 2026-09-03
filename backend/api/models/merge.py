import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class MergeType(str, enum.Enum):
    DIRECT = "direct"
    PR = "pr"


class PrStatus(str, enum.Enum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


class TaskMerge(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A task is Done only once this row exists. An orphan branch is unfinished work."""

    __tablename__ = "task_merges"

    task_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("tasks.id"), nullable=False, unique=True
    )
    type: Mapped[MergeType] = mapped_column(
        Enum(MergeType, native_enum=False, length=10), nullable=False
    )
    target_branch: Mapped[str] = mapped_column(String(200), nullable=False)

    merge_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pr_status: Mapped[PrStatus | None] = mapped_column(
        Enum(PrStatus, native_enum=False, length=10), nullable=True
    )
