"""SQLAlchemy field-kind detection, independent of transport and query adapters."""
from typing import Any

from sqlalchemy import String
from sqlalchemy.sql.sqltypes import (
    ARRAY, JSON, BigInteger, Boolean, Date, DateTime, Enum,
    Float, Integer, LargeBinary, Numeric, Time, Uuid,
)


def type_name(column: Any) -> str:
    t = column.type
    if isinstance(t, Boolean):
        return "boolean"
    if isinstance(t, (Integer, BigInteger)):
        return "integer"
    if isinstance(t, (Float, Numeric)):
        return "number"
    if isinstance(t, DateTime):
        return "datetime"
    if isinstance(t, Date):
        return "date"
    if isinstance(t, Time):
        return "time"
    if isinstance(t, Enum):
        return "enum"
    if isinstance(t, JSON):
        return "json"
    if isinstance(t, Uuid):
        return "uuid"
    if isinstance(t, ARRAY):
        return "array"
    if isinstance(t, LargeBinary):
        return "binary"
    if isinstance(t, String):
        return "string"
    return "string"
