"""Enums to use in API calls."""
import enum
from enum import Enum


class StrEnum(str, Enum):
    """Enum whose members' values are strings."""
    def __new__(cls, value: str) -> 'StrEnum':
        obj = str.__new__(cls, value)
        obj._value_ = value
        return obj


class APIEnum(StrEnum):
    """Enum customized for strings to pass to API.

    Takes something formatted like a Python variable and turns it into
    something formatted like a MW API parameter, by lowercasing and
    removing all underscores.
    """
    # pylint: disable-next=no-self-argument
    def _generate_next_value(name, _start, _count, _last_values) -> str:
        return name.lower().replace("_", "")


class Token(APIEnum):
    """Enums for API token types."""
    CREATE_ACCOUNT = enum.auto()
    CSRF = enum.auto()
    DELETE_GLOBAL_ACCOUNT = enum.auto()
    LOGIN = enum.auto()
    PATROL = enum.auto()
    ROLLBACK = enum.auto()
    SET_GLOBAL_ACCOUNT_STATUS = enum.auto()
    USER_RIGHTS = enum.auto()
    WATCH = enum.auto()
