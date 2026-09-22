import operator
from typing import Annotated, TypedDict

from models import DayWeather, FlightOffer, GroundOption, Place, StayOffer, Trip, TripSpec


class PlanState(TypedDict, total=False):
    user_query: str
    spec: TripSpec
    flights: list[FlightOffer]
    stays: list[StayOffer]
    weather: list[DayWeather]
    places: list[Place]
    ground: list[GroundOption]
    trip: Trip | None
    warnings: Annotated[list[str], operator.add]
    repair_count: int
    needs_repair: bool
