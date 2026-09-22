from pydantic import BaseModel


class Money(BaseModel):
    """Always store money as an integer minor unit (paise/cents), never a
    float — avoids rounding drift when totals get summed across many slots.
    """

    amount_minor: int
    currency: str = "INR"

    @property
    def amount(self) -> float:
        return self.amount_minor / 100

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} and {other.currency}")
        return Money(amount_minor=self.amount_minor + other.amount_minor, currency=self.currency)

    def __str__(self) -> str:
        return f"{self.currency} {self.amount:.2f}"
