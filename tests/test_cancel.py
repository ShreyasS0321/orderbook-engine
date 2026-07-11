"""Tests for OrderBook.cancel_order: removal, no-ops, partial fills, diary sync."""

from orderbook.book import OrderBook
from orderbook.types import Side


def test_cancel_resting_order_removes_it_from_the_book() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 50, Side.SELL)
    book.process_limit_order(2, 101, 20, Side.SELL)
    assert book.cancel_order(1) is True
    # the 100 level is gone; best ask moves up to 101
    assert book.ask_book.get_best_price() == 101
    assert book.ask_book.get_top_levels(5) == [(101, 20)]
    assert 1 not in book.order_diary


def test_cancel_unknown_id_is_a_noop() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 50, Side.SELL)
    assert book.cancel_order(999) is False
    assert book.ask_book.get_top_levels(1) == [(100, 50)]


def test_double_cancel_second_call_is_false() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 50, Side.SELL)
    assert book.cancel_order(1) is True
    assert book.cancel_order(1) is False


def test_cancel_partially_filled_order_removes_only_the_remainder() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 100, Side.SELL)
    book.process_limit_order(2, 100, 30, Side.BUY)  # fills 30 of o1, 70 left resting
    assert book.cancel_order(1) is True
    assert book.ask_book.is_empty()  # remaining 70 removed
    assert book.bid_book.is_empty()


def test_cancel_already_filled_order_is_a_noop() -> None:
    # Regression: a fully filled maker must be evicted from the diary so a later
    # cancel is a clean no-op instead of a KeyError.
    book = OrderBook()
    book.process_limit_order(1, 100, 50, Side.SELL)
    book.process_limit_order(2, 100, 50, Side.BUY)  # fully fills o1
    assert 1 not in book.order_diary
    assert book.cancel_order(1) is False


def test_incoming_order_does_not_trade_against_a_cancelled_order() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 50, Side.SELL)
    book.cancel_order(1)
    trades = book.process_limit_order(2, 100, 50, Side.BUY)
    assert trades == []  # nothing to trade against
    assert book.bid_book.get_best_price() == 100  # the buy rests instead


def test_cancel_on_the_bid_side() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 40, Side.BUY)
    book.process_limit_order(2, 99, 10, Side.BUY)
    assert book.cancel_order(1) is True
    assert book.bid_book.get_best_price() == 99
    assert book.bid_book.get_top_levels(5) == [(99, 10)]
