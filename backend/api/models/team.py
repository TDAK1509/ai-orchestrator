from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Team(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Who an agent belongs to, kept separate from Room (README Rule 2's room is where an agent is): membership does not change when a meeting starts."""

    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")
    # allow-comment: a team can never be hard-deleted once memory or agents reference it (see team_service.archive_team); this is the only way to remove one.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
