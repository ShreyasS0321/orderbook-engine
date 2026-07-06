# Requirements

This document describes what the matching engine must do. It deliberately avoids
saying *how* — data structures and algorithms live in `DESIGN.md`.

## Background

Every exchange sits on top of a limit order book. Buyers post bids, sellers post
asks, and a matching engine pairs them off according to a fixed set of rules. The
goal of this project is to reproduce that matching behaviour in memory, correctly
and deterministically, so it can later act as the core of a backtester or a trading
simulator.

## Scope

In scope: the matching engine itself. That means accepting orders, matching them,
tracking the ones that rest on the book, and reporting the resulting trades and book
state.

Out of scope, at least for this version: networking, persistence to disk, a user
interface, trading strategies, broker connectivity, coordinating more than one symbol
at a time, and thread-level concurrency. Some of these are likely follow-up projects;
none of them are needed to have a useful, testable engine.

## Users

There are really two consumers of this code. The first is another program — a
backtester, a simulator, or a test harness — that submits orders and reads back
trades and book state through a programmatic interface. The second is a person reading
the repository to judge whether the engine is correct and the code is any good.

## Functional requirements

Order submission

- FR-1: Accept a limit order with a side (buy or sell), a price, and a quantity.
- FR-2: Accept a market order with a side and a quantity but no price.
- FR-3: Every order carries a unique identifier so it can be referenced later.
- FR-4: Invalid orders are rejected clearly — non-positive quantity, unknown side, a
  limit order with no price, a market order with a price, or a duplicate identifier.

Matching

- FR-5: An incoming order matches against resting orders on the opposite side whenever
  the prices cross.
- FR-6: Matching follows price-time priority: best price first, and among orders at the
  same price, the one that arrived earliest.
- FR-7: Orders can fill partially. A single incoming order may be filled across several
  resting orders, and any unfilled remainder of a limit order rests on the book.
- FR-8: A market order takes liquidity until it is filled or the opposite side is empty.
  It never rests on the book.
- FR-9: Every execution produces a trade record with a price, a quantity, and the two
  orders involved.

Order lifecycle

- FR-10: A resting order can be cancelled by its identifier and removed from the book.
- FR-11: A resting order can be modified. Changing the quantity down keeps the order's
  place in line; increasing the quantity or changing the price sends it to the back of
  the queue at its price. The reasoning is in `DESIGN.md`.
- FR-12: Cancelling or modifying an order that no longer exists (already filled or
  cancelled) is handled gracefully and never corrupts the book.

Reporting

- FR-13: Report the best bid and best ask — price and available quantity — on demand.
- FR-14: Report the spread between best bid and best ask.
- FR-15: Report market depth: the aggregated quantity available at the top N price
  levels on each side.
- FR-16: Report that a side is empty when it holds no orders.

Guarantees

- FR-17: Given the same sequence of orders, the engine always produces the same trades
  and the same final book state. No randomness, no wall-clock time.
- FR-18: Quantity is conserved. Every unit is either resting, filled, or cancelled;
  none is created or lost.

## Non-functional requirements

- NFR-1, correctness: matching is verifiable against hand-worked examples and edge cases.
- NFR-2, performance: the engine processes a large stream of orders efficiently. Common
  operations (best price, add, cancel) should not degrade as the book grows. Concrete
  latency and throughput numbers are treated as a benchmark goal, not a hard gate.
- NFR-3, determinism: no reliance on wall-clock time, randomness, or run-to-run ordering.
- NFR-4, testability: all behaviour is reachable through a clear interface with no hidden
  state.
- NFR-5, reliability: bad input never leaves the book in an inconsistent state.
- NFR-6, clarity: the code and docs are readable by someone new to the project.
- NFR-7, precision: prices carry no floating-point rounding error.

## Constraints

- Python, standard tooling, no external services.
- Single symbol, single thread is acceptable for this version.
- In memory only. There is no requirement to persist or recover state.

## Assumptions

- Orders arrive in a defined sequence. The engine is not responsible for reordering them
  by real-world timestamps.
- Callers are trusted. No adversarial or security hardening is required here.
- Every order in a run concerns the same instrument.

## Definition of done

The project is finished when every functional requirement is demonstrably met; an
automated test suite covers price-time priority, partial fills, market orders, cancels,
modifies, and the obvious edge cases, and passes; a worked example from order stream to
trades to final book is documented and reproducible; the documentation explains what the
engine does, how to use it, and where its limits are; and determinism and quantity
conservation are checked by tests rather than asserted by hand.

## Deferred

Additional order types (IOC, FOK, stop orders), a latency benchmark harness, ingesting
real market data, and multi-symbol support are not requirements here. They are the most
likely next steps.
