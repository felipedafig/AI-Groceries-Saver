from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Store:
    dealer_id: str
    name: str
    street: str
    dist: float


@dataclass
class UnitPrice:
    value: float
    label: str


@dataclass
class ItemResult:
    query: str
    best_current: Optional[dict] = None
    best_future: Optional[dict] = None
    current_min_price: Optional[float] = None


@dataclass
class SearchResults:
    items: list[ItemResult] = field(default_factory=list)
    total: float = 0.0
    stores: dict[str, dict] = field(default_factory=dict)
