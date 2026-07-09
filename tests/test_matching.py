"""Tests for OrderBook limit-order matching: priority, fills, sweeps, invariants."""

from orderbook.book import OrderBook
from orderbook.types import Side

# --- resting (no cross) ----------------------------------------------------

def test_non_crossing_order_rests_without_trading() -> None:
    book = OrderBook()
    assert book.process_limit_order(1, 100, 10, Side.SELL) == []
    assert book.process_limit_order(2, 99, 10, Side.BUY) == []
    assert book.ask_book.get_best_price() == 100
    assert book.bid_book.get_best_price() == 99


def test_crossing_into_empty_side_just_rests() -> None:
    book = OrderBook()
    trades = book.process_limit_order(1, 100, 10, Side.BUY)
    assert trades == []
    assert book.bid_book.get_best_price() == 100


# --- basic fills -----------------------------------------------------------

def test_exact_match_fills_both_and_leaves_empty_book() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 50, Side.SELL)
    trades = book.process_limit_order(2, 100, 50, Side.BUY)
    assert len(trades) == 1
    assert trades[0].quantity == 50
    assert book.ask_book.is_empty()
    assert book.bid_book.is_empty()


def test_incoming_smaller_than_resting_partially_fills_resting() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 100, Side.SELL)
    trades = book.process_limit_order(2, 100, 30, Side.BUY)
    assert len(trades) == 1
    assert trades[0].quantity == 30
    # resting ask keeps 70, incoming fully filled so nothing rests on the bid
    assert book.ask_book.get_top_levels(1) == [(100, 70)]
    assert book.bid_book.is_empty()


def test_incoming_larger_than_resting_fills_then_rests_remainder() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 40, Side.SELL)
    trades = book.process_limit_order(2, 100, 100, Side.BUY)
    assert len(trades) == 1
    assert trades[0].quantity == 40
    assert book.ask_book.is_empty()
    # 60 of the buy is left resting on the bid side
    assert book.bid_book.get_top_levels(1) == [(100, 60)]


# --- price-time priority ---------------------------------------------------

def test_fifo_at_a_price_level() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 20, Side.SELL)
    book.process_limit_order(2, 100, 20, Side.SELL)
    trades = book.process_limit_order(3, 100, 20, Side.BUY)
    assert len(trades) == 1
    assert trades[0].maker_id == 1  # oldest order at the level fills first


def test_sweep_walks_price_levels_best_first() -> None:
    book = OrderBook()
    book.process_limit_order(1, 101, 10, Side.SELL)
    book.process_limit_order(2, 100, 10, Side.SELL)
    trades = book.process_limit_order(3, 101, 20, Side.BUY)
    assert [t.price for t in trades] == [100, 101]  # cheaper level consumed first


# --- maker price rule ------------------------------------------------------

def test_fill_happens_at_the_resting_makers_price() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 10, Side.SELL)
    trades = book.process_limit_order(2, 105, 10, Side.BUY)  # willing to pay 105
    assert trades[0].price == 100  # but trades at the maker's 100


# --- invariants ------------------------------------------------------------

def test_quantity_is_conserved_across_a_partial_sweep() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 30, Side.SELL)
    book.process_limit_order(2, 101, 30, Side.SELL)
    trades = book.process_limit_order(3, 101, 100, Side.BUY)
    filled = sum(t.quantity for t in trades)
    resting_bid = book.bid_book.get_top_levels(1)[0][1]
    assert filled == 60
    assert resting_bid == 40
    assert filled + resting_bid == 100  # nothing created or lost


def test_matching_is_deterministic() -> None:
    def run() -> list[tuple[int, int, int, int]]:
        book = OrderBook()
        book.process_limit_order(1, 100, 50, Side.SELL)
        book.process_limit_order(2, 101, 50, Side.SELL)
        trades = book.process_limit_order(3, 101, 80, Side.BUY)
        return [(t.maker_id, t.taker_id, t.price, t.quantity) for t in trades]

    assert run() == run()


def test_trade_ids_increment() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 10, Side.SELL)
    book.process_limit_order(2, 101, 10, Side.SELL)
    trades = book.process_limit_order(3, 101, 20, Side.BUY)
    assert [t.trade_id for t in trades] == [1, 2]


# --- tombstone tolerance ---------------------------------------------------

def test_matcher_skips_a_tombstone_at_the_front_of_a_level() -> None:
    book = OrderBook()
    book.process_limit_order(1, 100, 30, Side.SELL)  # will be cancelled
    book.process_limit_order(2, 100, 70, Side.SELL)  # stays live

    # Simulate a cancel of order 1: flag it and remove its volume once.
    book.order_diary[1].is_cancelled = True
    book.ask_book.reduce_volume(100, 30)

    trades = book.process_limit_order(3, 100, 70, Side.BUY)
    assert len(trades) == 1
    assert trades[0].maker_id == 2  # tombstone skipped, no trade against it
    assert trades[0].quantity == 70
    assert book.ask_book.is_empty()
