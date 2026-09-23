from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .money import Money


class TripSpec(BaseModel):
    """Structured intake, replacing the old free-text extract_destination()
    call. Fields the graph's clarify node treats as required: origin,
    (destination or suggest_destination), and (date_start or flexible_dates).
    """

    origin: str | None = None
    destination: str | None = None
    suggest_destination: bool = False
    date_start: date | None = None
    date_end: date | None = None
    flexible_dates: bool = False
    travelers: int = 1
    budget: Money | None = None
    pace: Literal["relaxed", "balanced", "packed"] = "balanced"
    # list[str] | None rather than a bare list[str]: Groq's strict
    # tool-schema validator rejected the model's own "nothing to put
    # here" output of `null` against a plain `"type": "array"` schema
    # (every intake call with no stated interests/constraints failed
    # validation). None is allowed at the schema level and normalized
    # back to [] below, so the rest of the codebase never has to
    # special-case None.
    interests: list[str] | None = Field(default=None)
    constraints: list[str] | None = Field(default=None)

    @model_validator(mode="after")
    def _normalize_none_lists(self) -> "TripSpec":
        if self.interests is None:
            self.interests = []
        if self.constraints is None:
            self.constraints = []
        return self

    def missing_required_fields(self) -> list[str]:
        missing = []
        if not self.origin:
            missing.append("origin")
        if not self.destination and not self.suggest_destination:
            missing.append("destination")
        if not self.date_start and not self.flexible_dates:
            missing.append("date_start")
        return missing

    def trip_length_days(self) -> int:
        if self.date_start and self.date_end:
            return max((self.date_end - self.date_start).days + 1, 1)
        return 1
