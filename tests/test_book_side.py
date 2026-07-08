"""Tests for HeapBookSide: ordering, FIFO, volume, ghost handling, cleanup."""

from orderbook.book_side import HeapBookSide
from orderbook.types import Order, OrderType, Side


def order(order_id: int, side: Side, price: int, qty: int) -> Order:
    """A resting limit order; timestamp tracks arrival order via order_id."""
    return Order(
        order_id=order_id,
        side=side,
        quantity=qty,
        timestamp=order_id,
        order_type=OrderType.LIMIT,
        price=price,
    )


# --- best price per side ---------------------------------------------------

def test_ask_side_best_price_is_lowest() -> None:
    asks = HeapBookSide(Side.SELL)
    asks.add_order(order(1, Side.SELL, 101, 10))
    asks.add_order(order(2, Side.SELL, 100, 10))
    asks.add_order(order(3, Side.SELL, 102, 10))
    assert asks.get_best_price() == 100


def test_bid_side_best_price_is_highest() -> None:
    bids = HeapBookSide(Side.BUY)
    bids.add_order(order(1, Side.BUY, 99, 10))
    bids.add_order(order(2, Side.BUY, 100, 10))
    bids.add_order(order(3, Side.BUY, 98, 10))
    assert bids.get_best_price() == 100


# --- FIFO within a level ---------------------------------------------------

def test_orders_at_a_price_come_out_in_arrival_order() -> None:
    asks = HeapBookSide(Side.SELL)
    asks.add_order(order(1, Side.SELL, 100, 10))
    asks.add_order(order(2, Side.SELL, 100, 20))
    assert asks.peek_best_order().order_id == 1
    assert asks.pop_best_order().order_id == 1
    assert asks.pop_best_order().order_id == 2


# --- volume tracking -------------------------------------------------------

def test_volume_aggregates_orders_at_a_level() -> None:
    asks = HeapBookSide(Side.SELL)
    asks.add_order(order(1, Side.SELL, 100, 30))
    asks.add_order(order(2, Side.SELL, 100, 20))
    assert asks.get_top_levels(1) == [(100, 50)]


def test_reduce_volume_is_reflected_in_depth() -> None:
    asks = HeapBookSide(Side.SELL)
    asks.add_order(order(1, Side.SELL, 100, 50))
    asks.reduce_volume(100, 20)
    assert asks.get_top_levels(1) == [(100, 30)]


# --- level cleanup (INV-4) -------------------------------------------------

def test_draining_a_level_removes_it_cleanly() -> None:
    asks = HeapBookSide(Side.SELL)
    asks.add_order(order(1, Side.SELL, 100, 10))
    asks.add_order(order(2, Side.SELL, 101, 10))
    asks.pop_best_order()  # drains the 100 level
    assert asks.get_best_price() == 101
    assert 100 not in asks.price_queue_dict
    assert 100 not in asks.volume_tracker


# --- ghost handling --------------------------------------------------------

def test_best_price_skips_a_dead_top_level() -> None:
    asks = HeapBookSide(Side.SELL)
    asks.add_order(order(1, Side.SELL, 100, 10))
    asks.add_order(order(2, Side.SELL, 101, 10))
    asks.reduce_volume(100, 10)  # 100 is now a ghost (no live volume)
    assert asks.get_best_price() == 101


def test_top_levels_skips_a_ghost_in_the_middle() -> None:
    asks = HeapBookSide(Side.SELL)
    asks.add_order(order(1, Side.SELL, 100, 10))
    asks.add_order(order(2, Side.SELL, 101, 10))
    asks.add_order(order(3, Side.SELL, 102, 10))
    asks.reduce_volume(101, 10)  # kill the middle level
    assert asks.get_top_levels(5) == [(100, 10), (102, 10)]


def test_top_levels_returns_at_most_n() -> None:
    asks = HeapBookSide(Side.SELL)
    for i, price in enumerate((100, 101, 102), start=1):
        asks.add_order(order(i, Side.SELL, price, 10))
    assert asks.get_top_levels(2) == [(100, 10), (101, 10)]


def test_top_levels_handles_request_larger_than_book() -> None:
    asks = HeapBookSide(Side.SELL)
    asks.add_order(order(1, Side.SELL, 100, 10))
    assert asks.get_top_levels(5) == [(100, 10)]


# --- tombstone popping does not double-count volume ------------------------

def test_popping_a_tombstone_does_not_reduce_volume_again() -> None:
    asks = HeapBookSide(Side.SELL)
    tombstone = order(1, Side.SELL, 100, 30)
    live = order(2, Side.SELL, 100, 70)
    asks.add_order(tombstone)
    asks.add_order(live)

    # Simulate a cancel of the first order: volume removed once, order flagged.
    asks.reduce_volume(100, 30)
    tombstone.is_cancelled = True
    assert asks.get_top_levels(1) == [(100, 70)]

    # Popping the tombstone must NOT subtract its 30 again.
    assert asks.pop_best_order().order_id == 1
    assert asks.get_top_levels(1) == [(100, 70)]

    # Popping the live order removes its volume and empties the level.
    assert asks.pop_best_order().order_id == 2
    assert asks.is_empty()


# --- empty side ------------------------------------------------------------

def test_empty_side_operations_do_not_crash() -> None:
    asks = HeapBookSide(Side.SELL)
    assert asks.is_empty() is True
    assert asks.get_best_price() is None
    assert asks.peek_best_order() is None
    assert asks.pop_best_order() is None
    assert asks.get_top_levels(5) == []
