"""
Date / time utility functions.
"""

from datetime import datetime


def parse_time(ts: str) -> datetime:
    """Parse an API timestamp string to a timezone-aware datetime.

    The Tjek API returns timestamps like ``2024-01-01T00:00:00+0000``.
    Python's ``fromisoformat`` requires the colon in the UTC offset,
    so we normalise it first.
    """
    return datetime.fromisoformat(ts.replace("+0000", "+00:00"))
