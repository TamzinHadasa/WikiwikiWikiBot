"""Utility functions."""
from dataclasses import dataclass
from typing import Optional


class MWAWError(Exception):
    """Base custom exception."""


@dataclass
class Page:
    """Wraps data generated by page-based API calls."""
    pageid: str
    namespace: int
    title: str
    lastrevid: int


class Revision:
    """Wraps data generated by revision-based API calls."""
    revid: Optional[str]
    userid: Optional[str]
    user: Optional[str]
    # TODO: __post_init__
