"""Tests for OrderBook.modify_order: in-place decrease vs cancel-and-replace."""

import pytest

from orderbook.book import OrderBook
from orderbook.types import Side


def test_modify_unknown_id_is_a_noop() -> None:
    book = OrderBook()
    assert book.modify_order(999, 100, 10) == []


def test_decrease_quantity_at_same_price_keeps_queue_position() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 20, Side.SELL)
    book.process_limit_order(2, 100, 20, Side.SELL)
    book.modify_order(1, 100, 10)  # decrease o1 in place
    assert book.best_ask() == (100, 30)  # 10 + 20
    # o1 keeps priority: an incoming buy still hits it first
    trades = book.process_limit_order(3, 100, 10, Side.BUY)
    assert trades[0].maker_id == 1


def test_increase_quantity_at_same_price_loses_queue_position() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 20, Side.SELL)
    book.process_limit_order(2, 100, 20, Side.SELL)
    book.modify_order(1, 100, 30)  # increase -> cancel-and-replace, o1 goes to back
    assert book.best_ask() == (100, 50)  # 20 (o2) + 30 (new o1)
    trades = book.process_limit_order(3, 100, 20, Side.BUY)
    assert trades[0].maker_id == 2  # o2 is now at the front


def test_price_change_moves_the_order_to_the_new_level() -> None:
    book = OrderBook()
    book.process_limit_order(1, 101, 20, Side.SELL)
    book.modify_order(1, 102, 20)
    assert book.best_ask() == (102, 20)


def test_modify_that_crosses_produces_trades() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 50, Side.BUY)   # resting bid
    book.process_limit_order(2, 105, 50, Side.SELL)  # resting ask, no cross
    # reprice the ask down to 100 -> it now crosses the bid
    trades = book.modify_order(2, 100, 50)
    assert len(trades) == 1
    assert trades[0].price == 100
    assert trades[0].maker_id == 1
    assert book.bid_book.is_empty()
    assert book.ask_book.is_empty()


def test_modify_to_zero_quantity_is_rejected() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 20, Side.SELL)
    with pytest.raises(ValueError):
        book.modify_order(1, 100, 0)


def test_partial_decrease_conserves_quantity() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 50, Side.BUY)
    book.modify_order(1, 100, 30)
    assert book.best_bid() == (100, 30)
