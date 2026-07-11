"""Tests for OrderBook.process_market_order: fill-and-kill, sweeps, no resting."""

from orderbook.book import OrderBook
from orderbook.types import Side


def test_market_buy_fills_against_best_ask() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 50, Side.SELL)
    trades = book.process_market_order(2, 50, Side.BUY)
    assert len(trades) == 1
    assert trades[0].price == 100
    assert trades[0].quantity == 50
    assert book.ask_book.is_empty()


def test_market_order_never_rests() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 30, Side.SELL)
    book.process_market_order(2, 100, Side.BUY)  # wants 100, only 30 available
    # 30 filled, remaining 70 dropped -- nothing rests on either side
    assert book.ask_book.is_empty()
    assert book.bid_book.is_empty()
    assert 2 not in book.order_diary


def test_market_order_into_empty_book_does_nothing() -> None:
    book = OrderBook()
    trades = book.process_market_order(1, 50, Side.BUY)
    assert trades == []
    assert book.ask_book.is_empty()
    assert book.bid_book.is_empty()


def test_market_buy_sweeps_multiple_levels_best_first() -> None:
    book = OrderBook()
    book.process_limit_order(1, 101, 10, Side.SELL)
    book.process_limit_order(2, 100, 10, Side.SELL)
    trades = book.process_market_order(3, 20, Side.BUY)
    assert [t.price for t in trades] == [100, 101]  # cheaper level first


def test_market_sell_fills_against_best_bid() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 40, Side.BUY)
    trades = book.process_market_order(2, 40, Side.SELL)
    assert len(trades) == 1
    assert trades[0].price == 100
    assert book.bid_book.is_empty()


def test_market_order_respects_price_time_priority() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 20, Side.SELL)
    book.process_limit_order(2, 100, 20, Side.SELL)
    trades = book.process_market_order(3, 20, Side.BUY)
    assert trades[0].maker_id == 1  # oldest at the level fills first


def test_market_buy_ignores_a_cancelled_resting_order() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 50, Side.SELL)
    book.cancel_order(1)
    trades = book.process_market_order(2, 50, Side.BUY)
    assert trades == []  # only liquidity was cancelled
    assert book.bid_book.is_empty()  # market order does not rest


def test_market_buy_partial_liquidity_fills_what_exists() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 30, Side.SELL)
    book.process_limit_order(2, 101, 40, Side.SELL)
    trades = book.process_market_order(3, 100, Side.BUY)  # 70 available, wants 100
    assert sum(t.quantity for t in trades) == 70  # fills all 70, drops the other 30
    assert book.ask_book.is_empty()
