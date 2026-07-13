from decimal import (
    MAX_EMAX,
    MIN_EMIN,
    Context,
    Decimal,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    localcontext,
)
from typing import Iterable


ZERO = Decimal("0")
CENT = Decimal("0.01")


def _validated_values(values: Iterable[Decimal]) -> tuple[Decimal, ...]:
    normalized = tuple(values)
    for value in normalized:
        if type(value) is not Decimal or not value.is_finite():
            raise ValueError("deterministic Decimal arithmetic requires finite Decimal values")
    return normalized


def required_precision(
    values: Iterable[Decimal],
    *,
    target_exponent: int | None = None,
    guard_digits: int = 8,
) -> int:
    normalized = _validated_values(values)
    if not normalized:
        return guard_digits

    exponents = [int(value.as_tuple().exponent) for value in normalized]
    if target_exponent is not None:
        exponents.append(target_exponent)
    minimum_exponent = min(exponents)
    maximum_adjusted = max(value.adjusted() for value in normalized)
    aligned_digits = maximum_adjusted - minimum_exponent + 1
    coefficient_digits = max(
        len(value.as_tuple().digits) for value in normalized
    )
    carry_digits = len(str(len(normalized)))
    return max(
        guard_digits,
        aligned_digits + carry_digits + guard_digits,
        coefficient_digits + carry_digits + guard_digits,
    )


def working_precision(
    values: Iterable[Decimal],
    *,
    guard_digits: int = 50,
) -> int:
    normalized = _validated_values(values)
    coefficient_product_digits = sum(
        len(value.as_tuple().digits) for value in normalized
    )
    return max(
        required_precision(normalized, guard_digits=guard_digits),
        coefficient_product_digits + guard_digits,
    )


def configure_context(context: Context, precision: int) -> None:
    context.prec = precision
    context.rounding = ROUND_HALF_EVEN
    context.Emax = MAX_EMAX
    context.Emin = MIN_EMIN
    context.clamp = 0


def exact_sum(values: Iterable[Decimal]) -> Decimal:
    normalized = _validated_values(values)
    if not normalized:
        return ZERO

    with localcontext() as context:
        configure_context(context, required_precision(normalized))
        total = ZERO
        for value in normalized:
            total += value
        return total


def exact_difference(minuend: Decimal, subtrahend: Decimal) -> Decimal:
    return exact_sum((minuend, subtrahend.copy_negate()))


def quantize_money(value: Decimal) -> Decimal:
    normalized = _validated_values((value,))
    with localcontext() as context:
        configure_context(
            context,
            required_precision(
                (*normalized, CENT),
                target_exponent=int(CENT.as_tuple().exponent),
            ),
        )
        return value.quantize(CENT, rounding=ROUND_HALF_UP)
