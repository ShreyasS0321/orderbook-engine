"""Tests for the core data types: fixed-point conversion, validation, immutability."""

from dataclasses import FrozenInstanceError

import pytest

from orderbook.types import Order, OrderType, Side, Trade, from_ticks, to_ticks


def make_limit(**overrides: object) -> Order:
    """A valid limit order, with fields overridable per test."""
    defaults: dict[str, object] = {
        "order_id": 1,
        "side": Side.BUY,
        "quantity": 100,
        "timestamp": 0,
        "order_type": OrderType.LIMIT,
        "price": to_ticks(101.50),
    }
    defaults.update(overrides)
    return Order(**defaults)  # type: ignore[arg-type]


# --- fixed-point helpers ---------------------------------------------------

def test_to_ticks_converts_price_to_scaled_int() -> None:
    assert to_ticks(101.50) == 10_150_000


def test_from_ticks_converts_back_to_price() -> None:
    assert from_ticks(10_150_000) == 101.50


def test_price_round_trips_without_drift() -> None:
    # 0.1 has no exact float representation; the round() in to_ticks must
    # absorb that so the value survives a round trip.
    assert from_ticks(to_ticks(0.1)) == 0.1


# --- validation (__post_init__) --------------------------------------------

def test_zero_quantity_rejected() -> None:
    with pytest.raises(ValueError):
        make_limit(quantity=0)


def test_negative_quantity_rejected() -> None:
    with pytest.raises(ValueError):
        make_limit(quantity=-5)


def test_limit_order_requires_a_price() -> None:
    with pytest.raises(ValueError):
        make_limit(price=None)


def test_market_order_must_not_have_a_price() -> None:
    with pytest.raises(ValueError):
        make_limit(order_type=OrderType.MARKET, price=to_ticks(101.50))


def test_valid_limit_order_constructs() -> None:
    order = make_limit()
    assert order.order_type is OrderType.LIMIT
    assert order.price == to_ticks(101.50)
    assert order.is_cancelled is False


def test_valid_market_order_constructs() -> None:
    order = make_limit(order_type=OrderType.MARKET, price=None)
    assert order.order_type is OrderType.MARKET
    assert order.price is None


# --- immutability ----------------------------------------------------------

def test_trade_is_immutable() -> None:
    trade = Trade(
        trade_id=1,
        maker_id=10,
        taker_id=20,
        price=to_ticks(101.50),
        quantity=50,
        timestamp=0,
    )
    with pytest.raises(FrozenInstanceError):
        trade.price = to_ticks(102.00)  # type: ignore[misc]
