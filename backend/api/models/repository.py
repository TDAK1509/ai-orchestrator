from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Repository(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A git repository a task's worktree can be cut from (README 14's "Repository / workspace" field)."""

    __tablename__ = "repositories"

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    default_target_branch: Mapped[str] = mapped_column(String(200), nullable=False, default="origin/main")
    # allow-comment: unused until a repo's worktree needs bootstrapping (e.g. installing dependencies); carried now per plan-multirepo-and-chat.md appendix so adding it later isn't a migration.
    default_working_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)
    setup_script: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
