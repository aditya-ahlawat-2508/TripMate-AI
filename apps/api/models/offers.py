from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from .money import Money
from .source import Source


class FlightOffer(BaseModel):
    id: str
    airline: str
    dep_iata: str
    arr_iata: str
    depart_at: datetime | None = None
    arrive_at: datetime | None = None
    duration_minutes: int | None = None
    price: Money | None = None
    source: Source


class StayOffer(BaseModel):
    id: str
    name: str
    rating: float | None = None
    lat: float | None = None
    lng: float | None = None
    price_per_night: Money | None = None
    source: Source


class DayWeather(BaseModel):
    date: date
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    condition: str = "unknown"
    precipitation_mm: float | None = None
    is_historical_average: bool = False


class Place(BaseModel):
    id: str
    name: str
    category: str
    lat: float
    lng: float
    source: Source


class GroundOption(BaseModel):
    mode: Literal["rail", "bus", "cab", "unavailable"]
    description: str
    price: Money | None = None
    source: Source
