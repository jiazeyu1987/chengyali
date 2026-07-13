from calendar import monthrange
from dataclasses import dataclass
from datetime import date

from .errors import DomainError, DomainErrorCode, DomainValidationError


@dataclass(frozen=True, slots=True)
class NaturalMonth:
    year: int
    month: int

    def __post_init__(self) -> None:
        if type(self.year) is not int or type(self.month) is not int:
            self._raise_invalid("year and month must be integers")
        if self.year < 1 or self.year > 9999 or self.month < 1 or self.month > 12:
            self._raise_invalid("year or month is outside the calendar range")

    @property
    def start_date(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def end_date(self) -> date:
        return date(self.year, self.month, monthrange(self.year, self.month)[1])

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1

    def contains(self, value: date) -> bool:
        return self.start_date <= value <= self.end_date

    def _raise_invalid(self, message: str) -> None:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.PERIOD_INVALID,
                column_or_field="calculation_month",
                message=message,
            )
        )
