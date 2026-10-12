from decimal import Decimal

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from app.core.allocation import (
    AllocationError,
    Share,
    allocate_by_percentage,
    allocate_fixed,
    largest_remainder,
)

MAX_PAISA = 99_999_999_999_999


def paisa_of(shares: list[Share]) -> dict[int, int]:
    return {share.bucket_id: share.paisa for share in shares}


@st.composite
def allocation_inputs(draw: st.DrawFn) -> tuple[int, list[tuple[int, int]]]:
    total = draw(st.integers(min_value=1, max_value=MAX_PAISA))
    ids = draw(st.lists(st.integers(min_value=1, max_value=10_000), min_size=1, max_size=12, unique=True))
    weights = [draw(st.integers(min_value=0, max_value=10_000)) for _ in ids]
    assume(sum(weights) > 0)
    return total, list(zip(ids, weights, strict=True))


# Worked examples -----------------------------------------------------------------------------------------------------


def test_equal_thirds_give_the_extra_paisa_to_the_lowest_id() -> None:
    shares = largest_remainder(10_000, [(3, 1), (1, 1), (2, 1)])
    assert paisa_of(shares) == {1: 3334, 2: 3333, 3: 3333}


def test_leftover_goes_to_the_largest_remainder_not_the_largest_share() -> None:
    # Ideal shares 1.47, 1.47, 0.06 of 3 paisa: floors 1, 1, 0; one left over, and ids 1 and 2 tie on remainder.
    assert paisa_of(largest_remainder(3, [(1, 49), (2, 49), (3, 2)])) == {1: 2, 2: 1, 3: 0}
    # Ideal 2.1, 2.7, 0.2 of 5: the remainder 0.7 outranks 0.2 and 0.1, whatever the order of the input.
    assert paisa_of(largest_remainder(5, [(1, 21), (2, 27), (3, 2)])) == {1: 2, 2: 3, 3: 0}
    assert paisa_of(largest_remainder(5, [(3, 2), (2, 27), (1, 21)])) == {1: 2, 2: 3, 3: 0}


def test_one_paisa_goes_to_the_largest_remainder() -> None:
    assert paisa_of(largest_remainder(1, [(1, 5000), (2, 3000), (3, 2000)])) == {1: 1, 2: 0, 3: 0}


def test_result_follows_input_order() -> None:
    assert [s.bucket_id for s in largest_remainder(100, [(9, 1), (4, 1), (7, 1)])] == [9, 4, 7]


def test_percentage_strategy_works_in_rupees() -> None:
    shares = allocate_by_percentage(Decimal("100.00"), [(1, 3333), (2, 3333), (3, 3334)])
    assert [s.amount for s in shares] == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
    assert sum(s.amount for s in shares) == Decimal("100.00")


def test_percentage_strategy_requires_exactly_ten_thousand() -> None:
    with pytest.raises(AllocationError):
        allocate_by_percentage(Decimal("100.00"), [(1, 5000), (2, 4999)])
    with pytest.raises(AllocationError):
        allocate_by_percentage(Decimal("100.00"), [(1, 5000), (2, 5001)])


def test_fixed_strategy_uses_the_amounts_as_given() -> None:
    shares = allocate_fixed(Decimal("100.00"), [(1, Decimal("60.10")), (2, Decimal("39.90"))])
    assert paisa_of(shares) == {1: 6010, 2: 3990}


def test_fixed_strategy_requires_the_exact_total() -> None:
    with pytest.raises(AllocationError):
        allocate_fixed(Decimal("100.00"), [(1, Decimal("60.00")), (2, Decimal("39.99"))])
    with pytest.raises(AllocationError):
        allocate_fixed(Decimal("100.00"), [(1, Decimal("60.00")), (2, Decimal("40.01"))])


# Edges ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("total", "weights", "message"),
    [
        (100, [], "at least one bucket"),
        (100, [(1, 1), (1, 2)], "unique"),
        (100, [(1, 0), (2, 0)], "at least one weight"),
        (0, [(1, 1)], "positive"),
        (-5, [(1, 1)], "positive"),
        (100, [(1, -1), (2, 2)], "negative"),
    ],
    ids=["empty", "duplicate ids", "all zero weights", "zero total", "negative total", "negative weight"],
)
def test_invalid_inputs_raise(total: int, weights: list[tuple[int, int]], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        largest_remainder(total, weights)


def test_a_zero_weight_receives_zero() -> None:
    assert paisa_of(largest_remainder(100, [(1, 0), (2, 1), (3, 1)]))[1] == 0


# Properties ----------------------------------------------------------------------------------------------------------


@given(allocation_inputs())
def test_parts_sum_to_the_total_and_are_integers(data: tuple[int, list[tuple[int, int]]]) -> None:
    total, weights = data
    shares = largest_remainder(total, weights)
    assert sum(s.paisa for s in shares) == total
    assert all(type(s.paisa) is int and s.paisa >= 0 for s in shares)


@given(allocation_inputs())
def test_each_part_is_within_one_paisa_of_its_ideal(data: tuple[int, list[tuple[int, int]]]) -> None:
    total, weights = data
    weight_sum = sum(w for _, w in weights)
    weight_of = dict(weights)
    for share in largest_remainder(total, weights):
        # |share - total * w / S| < 1, written without division
        assert abs(share.paisa * weight_sum - total * weight_of[share.bucket_id]) < weight_sum


@given(allocation_inputs(), st.data())
def test_result_is_stable_under_reordering(inputs: tuple[int, list[tuple[int, int]]], data: st.DataObject) -> None:
    total, weights = inputs
    shuffled = data.draw(st.permutations(weights))
    assert paisa_of(largest_remainder(total, weights)) == paisa_of(largest_remainder(total, shuffled))


@given(allocation_inputs())
def test_zero_weight_stays_zero(data: tuple[int, list[tuple[int, int]]]) -> None:
    total, weights = data
    weight_of = dict(weights)
    for share in largest_remainder(total, weights):
        if weight_of[share.bucket_id] == 0:
            assert share.paisa == 0


@given(allocation_inputs())
def test_allocation_is_idempotent(data: tuple[int, list[tuple[int, int]]]) -> None:
    total, weights = data
    first = largest_remainder(total, weights)
    assert largest_remainder(total, weights) == first
    # Using the result as the weights reproduces it: the ideal shares are then whole numbers.
    assert largest_remainder(total, [(s.bucket_id, s.paisa) for s in first]) == first


@given(allocation_inputs())
def test_buckets_that_received_a_leftover_outrank_those_that_did_not(
    data: tuple[int, list[tuple[int, int]]],
) -> None:
    total, weights = data
    weight_sum = sum(w for _, w in weights)
    weight_of = dict(weights)
    winners: list[tuple[int, int]] = []
    others: list[tuple[int, int]] = []
    for share in largest_remainder(total, weights):
        floor, remainder = divmod(total * weight_of[share.bucket_id], weight_sum)
        assert share.paisa in (floor, floor + 1)
        (winners if share.paisa == floor + 1 else others).append((-remainder, share.bucket_id))
    # Rank is remainder descending, then id ascending: every winner sorts before every non-winner.
    for winner in winners:
        for other in others:
            assert winner < other
