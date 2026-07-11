"""Tests for OrderBook reporting: best bid/ask, spread, depth."""

from orderbook.book import OrderBook
from orderbook.types import Side


def test_empty_book_reports_nothing() -> None:
    book = OrderBook()
    assert book.best_bid() is None
    assert book.best_ask() is None
    assert book.spread() is None
    assert book.depth(5) == ([], [])


def test_best_bid_and_ask_give_price_and_quantity() -> None:
    book = OrderBook()
    book.process_limit_order(1, 99, 30, Side.BUY)
    book.process_limit_order(2, 101, 40, Side.SELL)
    assert book.best_bid() == (99, 30)
    assert book.best_ask() == (101, 40)


def test_best_bid_aggregates_quantity_at_the_level() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 30, Side.BUY)
    book.process_limit_order(2, 100, 20, Side.BUY)
    assert book.best_bid() == (100, 50)


def test_spread_is_ask_minus_bid() -> None:
    book = OrderBook()
    book.process_limit_order(1, 99, 10, Side.BUY)
    book.process_limit_order(2, 101, 10, Side.SELL)
    assert book.spread() == 2


def test_spread_is_none_when_a_side_is_empty() -> None:
    book = OrderBook()
    book.process_limit_order(1, 99, 10, Side.BUY)
    assert book.spread() is None


def test_depth_returns_both_ladders_best_first() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 10, Side.BUY)
    book.process_limit_order(2, 99, 20, Side.BUY)
    book.process_limit_order(3, 101, 15, Side.SELL)
    book.process_limit_order(4, 102, 25, Side.SELL)
    bids, asks = book.depth(5)
    assert bids == [(100, 10), (99, 20)]
    assert asks == [(101, 15), (102, 25)]


def test_depth_caps_at_n_levels() -> None:
    book = OrderBook()
    for i, price in enumerate((100, 99, 98), start=1):
        book.process_limit_order(i, price, 10, Side.BUY)
    bids, _ = book.depth(2)
    assert bids == [(100, 10), (99, 10)]
