import datetime
import enum
import uuid

from sqlalchemy import inspect


def serialize(record) -> dict:
    mapper = inspect(record).mapper
    return {column.key: serialize_value(getattr(record, column.key)) for column in mapper.columns}


def serialize_value(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    return value
