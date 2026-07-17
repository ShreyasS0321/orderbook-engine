"""Deterministic order-flow generation and replay.

A seed fully determines the command stream, so every backend sees the identical
sequence -- the basis for both fair benchmarking and differential testing.
"""

import random
from enum import Enum
from typing import NamedTuple

from orderbook.book import OrderBook
from orderbook.types import Side, Trade


class Action(Enum):
    LIMIT = 1
    MARKET = 2
    CANCEL = 3
    MODIFY = 4


class Command(NamedTuple):
    action: Action
    order_id: int
    side: Side | None = None
    price: int | None = None
    quantity: int | None = None
    new_price: int | None = None
    new_quantity: int | None = None


def generate(
    n: int,
    *,
    seed: int = 0,
    mid: int = 100_000,
    max_offset: int = 20,
    max_quantity: int = 100,
    p_limit: float = 0.55,
    p_market: float = 0.05,
    p_cancel: float = 0.30,
    aggressive_rate: float = 0.15,
) -> list[Command]:
    """Generate n commands.

    Prices cluster near `mid` (geometric distance), the mix is add/cancel-heavy
    like a real feed, and cancels/modifies target orders that were actually
    added. p_modify is implied as the remainder of the probabilities.
    """
    rng = random.Random(seed)
    commands: list[Command] = []
    live_ids: list[int] = []
    next_id = 1

    def offset() -> int:
        return min(int(rng.expovariate(0.5)), max_offset)

    for _ in range(n):
        r = rng.random()
        has_live = bool(live_ids)

        if r < p_limit or not has_live:
            side = rng.choice((Side.BUY, Side.SELL))
            qty = rng.randint(1, max_quantity)
            off = offset()
            aggressive = rng.random() < aggressive_rate
            if side is Side.BUY:
                price = mid + off if aggressive else mid - off
            else:
                price = mid - off if aggressive else mid + off
            oid = next_id
            next_id += 1
            commands.append(Command(Action.LIMIT, oid, side=side, price=price, quantity=qty))
            live_ids.append(oid)
        elif r < p_limit + p_market:
            side = rng.choice((Side.BUY, Side.SELL))
            qty = rng.randint(1, max_quantity)
            oid = next_id
            next_id += 1
            commands.append(Command(Action.MARKET, oid, side=side, quantity=qty))
        elif r < p_limit + p_market + p_cancel:
            commands.append(Command(Action.CANCEL, rng.choice(live_ids)))
        else:
            oid = rng.choice(live_ids)
            commands.append(
                Command(
                    Action.MODIFY,
                    oid,
                    new_price=mid + offset(),
                    new_quantity=rng.randint(1, max_quantity),
                )
            )

    return commands


def replay(commands: list[Command], book: OrderBook) -> list[list[Trade] | bool]:
    """Run a command stream through a book, returning each command's result."""
    results: list[list[Trade] | bool] = []
    for c in commands:
        if c.action is Action.LIMIT:
            results.append(book.process_limit_order(c.order_id, c.price, c.quantity, c.side))
        elif c.action is Action.MARKET:
            results.append(book.process_market_order(c.order_id, c.quantity, c.side))
        elif c.action is Action.CANCEL:
            results.append(book.cancel_order(c.order_id))
        else:
            results.append(book.modify_order(c.order_id, c.new_price, c.new_quantity))
    return results
