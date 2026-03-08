"""
Data classes representing domain objects used across the application.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Store:
    """Represents a nearby grocery store."""

    dealer_id: str
    name: str
    street: str
    dist: float  # distance in km


@dataclass
class UnitPrice:
    """Represents a calculated unit price with its label."""

    value: float  # e.g. 50.0
    label: str    # e.g. 'kr/kg'


@dataclass
class ItemResult:
    """Holds the search results for a single grocery item."""

    query: str
    best_current: Optional[dict] = None
    best_future: Optional[dict] = None
    current_min_price: Optional[float] = None


@dataclass
class SearchResults:
    """Aggregated search results for all items."""

    items: list[ItemResult] = field(default_factory=list)
    total: float = 0.0
    stores: dict[str, dict] = field(default_factory=dict)
