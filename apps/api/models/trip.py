from datetime import date, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from .money import Money
from .offers import DayWeather
from .source import Source


class Slot(BaseModel):
    start: time
    end: time
    kind: Literal["activity", "meal", "transit", "stay"]
    place_id: str | None = None
    title: str
    lat: float | None = None
    lng: float | None = None
    cost: Money | None = None
    source: Source | None = None
    notes: str | None = None


class Day(BaseModel):
    date: date
    weather: DayWeather | None = None
    slots: list[Slot] = Field(default_factory=list)


class BudgetBreakdown(BaseModel):
    total: Money
    limit: Money | None = None
    by_category: dict[str, Money] = Field(default_factory=dict)
    fits_budget: bool | None = None


class Trip(BaseModel):
    id: UUID
    spec: "TripSpec"
    flights: list["FlightOffer"] = Field(default_factory=list)
    stays: list["StayOffer"] = Field(default_factory=list)
    days: list[Day] = Field(default_factory=list)
    budget: BudgetBreakdown
    warnings: list[str] = Field(default_factory=list)
    version: int = 1


from .offers import FlightOffer, StayOffer  # noqa: E402
from .trip_spec import TripSpec  # noqa: E402

Trip.model_rebuild()
