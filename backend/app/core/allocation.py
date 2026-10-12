"""Splitting an indirect expense across cost centres. Integer paisa only, so the parts always sum to the total.

Largest remainder: every bucket gets the floor of its ideal share; the paisa left over go one each to the buckets with
the largest fractional remainders, ties broken by bucket id ascending so the same cost centre receives the extra paisa
on every recalculation. Division happens only here and in money.py.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.core.money import BASIS_POINTS_TOTAL, from_paisa, to_paisa


class AllocationError(ValueError):
    """The inputs cannot be allocated. Services check first and report a field error; this guards the function."""


@dataclass(frozen=True)
class Share:
    bucket_id: int
    paisa: int

    @property
    def amount(self) -> Decimal:
        return from_paisa(self.paisa)


def largest_remainder(total_paisa: int, weights: Sequence[tuple[int, int]]) -> list[Share]:
    """Split ``total_paisa`` over ``(bucket_id, weight)`` pairs. The result follows the input order."""
    if not weights:
        raise AllocationError("at least one bucket is required")
    if total_paisa <= 0:
        raise AllocationError("the total must be positive")
    ids = [bucket_id for bucket_id, _ in weights]
    if len(set(ids)) != len(ids):
        raise AllocationError("bucket ids must be unique")
    if any(weight < 0 for _, weight in weights):
        raise AllocationError("weights must not be negative")
    weight_sum = sum(weight for _, weight in weights)
    if weight_sum == 0:
        raise AllocationError("at least one weight must be positive")

    floors: dict[int, int] = {}
    remainders: dict[int, int] = {}
    for bucket_id, weight in weights:
        floors[bucket_id], remainders[bucket_id] = divmod(total_paisa * weight, weight_sum)

    leftover = total_paisa - sum(floors.values())
    # Remainders share the denominator `weight_sum`, so comparing the integer numerators compares the fractions.
    ranked = sorted((b for b in ids if remainders[b] > 0), key=lambda b: (-remainders[b], b))
    for bucket_id in ranked[:leftover]:
        floors[bucket_id] += 1
    return [Share(bucket_id, floors[bucket_id]) for bucket_id in ids]


def allocate_by_percentage(total: Decimal, percentages: Sequence[tuple[int, int]]) -> list[Share]:
    """Percentage strategy. ``percentages`` are ``(bucket_id, basis_points)`` and must sum to exactly 10,000."""
    if sum(bps for _, bps in percentages) != BASIS_POINTS_TOTAL:
        raise AllocationError("percentages must sum to exactly 10,000 basis points")
    return largest_remainder(to_paisa(total), percentages)


def allocate_fixed(total: Decimal, amounts: Sequence[tuple[int, Decimal]]) -> list[Share]:
    """Fixed-amount strategy. The amounts are used as given and must sum to exactly the total."""
    if not amounts:
        raise AllocationError("at least one bucket is required")
    ids = [bucket_id for bucket_id, _ in amounts]
    if len(set(ids)) != len(ids):
        raise AllocationError("bucket ids must be unique")
    total_paisa = to_paisa(total)
    if total_paisa <= 0:
        raise AllocationError("the total must be positive")
    shares = [Share(bucket_id, to_paisa(amount)) for bucket_id, amount in amounts]
    if any(share.paisa < 0 for share in shares):
        raise AllocationError("amounts must not be negative")
    if sum(share.paisa for share in shares) != total_paisa:
        raise AllocationError("fixed amounts must sum to exactly the total")
    return shares
