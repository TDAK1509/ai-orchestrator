import enum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RoomType(str, enum.Enum):
    MAIN = "main"
    MEETING = "meeting"


class Room(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Where an agent is, kept separate from what it's doing (README Rule 2): status and room never merge into one field."""

    __tablename__ = "rooms"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[RoomType] = mapped_column(Enum(RoomType, native_enum=False, length=10), nullable=False)
