"""Tests for entry validation: duplicate ids and non-positive quantities."""

import pytest

from orderbook.book import OrderBook
from orderbook.types import Side


def test_duplicate_id_of_a_resting_order_is_rejected() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 10, Side.SELL)
    with pytest.raises(ValueError):
        book.process_limit_order(1, 101, 10, Side.SELL)


def test_market_order_with_duplicate_id_is_rejected() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 10, Side.BUY)
    with pytest.raises(ValueError):
        book.process_market_order(1, 5, Side.SELL)


def test_zero_quantity_is_rejected() -> None:
    book = OrderBook()
    with pytest.raises(ValueError):
        book.process_limit_order(1, 100, 0, Side.BUY)
    with pytest.raises(ValueError):
        book.process_market_order(2, 0, Side.BUY)


def test_negative_quantity_is_rejected() -> None:
    book = OrderBook()
    with pytest.raises(ValueError):
        book.process_limit_order(1, 100, -5, Side.BUY)


def test_valid_order_is_accepted() -> None:
    book = OrderBook()
    assert book.process_limit_order(1, 100, 10, Side.BUY) == []


def test_id_can_be_reused_once_the_order_has_left_the_book() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 10, Side.SELL)
    book.process_limit_order(2, 100, 10, Side.BUY)  # fully fills id 1, evicting it
    assert 1 not in book.order_diary
    # id 1 is free again
    book.process_limit_order(1, 105, 10, Side.SELL)
    assert book.best_ask() == (105, 10)
