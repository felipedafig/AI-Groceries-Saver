from datetime import datetime


def parse_time(ts: str) -> datetime:
    """Parse an API timestamp to a timezone-aware datetime."""
    return datetime.fromisoformat(ts.replace("+0000", "+00:00"))
