from calendar import monthrange
from dataclasses import dataclass
from datetime import date

from .errors import DomainError, DomainErrorCode, DomainValidationError


@dataclass(frozen=True, slots=True)
class NaturalMonth:
    year: int
    month: int
    end_year: int | None = None
    end_month: int | None = None
    start_day: int | None = None
    end_day: int | None = None

    def __post_init__(self) -> None:
        if type(self.year) is not int or type(self.month) is not int:
            self._raise_invalid("year and month must be integers")
        if self.year < 1 or self.year > 9999 or self.month < 1 or self.month > 12:
            self._raise_invalid("year or month is outside the calendar range")
        if (self.end_year is None) != (self.end_month is None):
            self._raise_invalid("end year and end month must be provided together")
        if (self.start_day is None) != (self.end_day is None):
            self._raise_invalid("start day and end day must be provided together")
        if self.end_year is not None and self.end_month is not None:
            if (
                type(self.end_year) is not int
                or type(self.end_month) is not int
                or self.end_year < 1
                or self.end_year > 9999
                or self.end_month < 1
                or self.end_month > 12
            ):
                self._raise_invalid("end year or end month is outside the calendar range")
        try:
            start_date = self.start_date
            end_date = self.end_date
        except ValueError:
            self._raise_invalid("start date or end date is outside the calendar range")
        if end_date < start_date:
            self._raise_invalid("end date must not precede start date")

    @property
    def start_date(self) -> date:
        return date(self.year, self.month, self.start_day or 1)

    @property
    def end_date(self) -> date:
        year = self.end_year if self.end_year is not None else self.year
        month = self.end_month if self.end_month is not None else self.month
        day = self.end_day or monthrange(year, month)[1]
        return date(year, month, day)

    @property
    def is_exact_date_range(self) -> bool:
        return self.start_day is not None

    @property
    def is_single_month(self) -> bool:
        return (
            self.end_year is None
            or (self.end_year, self.end_month) == (self.year, self.month)
        )

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
