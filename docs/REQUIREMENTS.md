# Requirements

What the matching engine must do. The *how* (data structures, algorithms) is in
`DESIGN.md`.

## Background

Every exchange sits on a limit order book: buyers post bids, sellers post asks, and a
matching engine pairs them by a fixed set of rules. This project reproduces that matching
in memory, correctly and deterministically, so it can later back a backtester or a
trading simulator.

## Scope

In scope: the matching engine. Accept orders, match them, track resting orders, report
trades and book state.

Out of scope for this version: networking, persistence, a UI, trading strategies, broker
connectivity, multiple symbols, and thread concurrency. Some are likely follow-ups; none
are needed for a useful, testable engine.

## Users

Two consumers. A program (backtester, simulator, test harness) that submits orders and
reads back trades and book state through a programmatic interface. And a person reading
the repo to judge whether the engine is correct and the code is any good.

## Functional requirements

Order submission

- FR-1: Accept a limit order with a side (buy or sell), a price, and a quantity.
- FR-2: Accept a market order with a side and a quantity but no price.
- FR-3: Every order carries a unique identifier so it can be referenced later.
- FR-4: Reject invalid orders clearly: non-positive quantity, unknown side, a limit order
  with no price, a market order with a price, or a duplicate identifier.

Matching

- FR-5: An incoming order matches resting orders on the opposite side whenever prices cross.
- FR-6: Matching follows price-time priority: best price first, earliest arrival among
  orders at the same price.
- FR-7: Orders can fill partially. One incoming order may fill across several resting
  orders; any unfilled remainder of a limit order rests on the book.
- FR-8: A market order takes liquidity until filled or the opposite side is empty. It never
  rests.
- FR-9: Every execution produces a trade record with a price, a quantity, and the two
  orders involved.

Order lifecycle

- FR-10: A resting order can be cancelled by its identifier and removed from the book.
- FR-11: A resting order can be modified. Decreasing quantity keeps its place in line;
  increasing quantity or changing price sends it to the back of the queue at its price.
  Reasoning is in `DESIGN.md`.
- FR-12: Cancelling or modifying an order that no longer exists (already filled or
  cancelled) is a no-op and never corrupts the book.

Reporting

- FR-13: Report best bid and best ask (price and available quantity) on demand.
- FR-14: Report the spread between best bid and best ask.
- FR-15: Report market depth: aggregated quantity at the top N price levels per side.
- FR-16: Report that a side is empty when it holds no orders.

Guarantees

- FR-17: Same sequence of orders in, same trades and same final book out. No randomness,
  no wall-clock time.
- FR-18: Quantity is conserved. Every unit is resting, filled, or cancelled; none created
  or lost.

## Non-functional requirements

- NFR-1 correctness: matching is verifiable against hand-worked examples and edge cases.
- NFR-2 performance: common operations (best price, add, cancel) do not degrade as the book
  grows. Concrete latency/throughput numbers are a benchmark goal, not a hard gate.
- NFR-3 determinism: no wall-clock time, randomness, or run-to-run ordering.
- NFR-4 testability: all behaviour reachable through a clear interface, no hidden state.
- NFR-5 reliability: bad input never leaves the book inconsistent.
- NFR-6 clarity: code and docs readable by someone new to the project.
- NFR-7 precision: prices carry no floating-point rounding error.

## Constraints

- Python, standard tooling, no external services.
- Single symbol, single thread is fine for this version.
- In memory only; no persistence or recovery required.

## Assumptions

- Orders arrive in a defined sequence. The engine does not reorder them by real-world time.
- Callers are trusted. No adversarial hardening.
- Every order in a run concerns the same instrument.

## Definition of done

- Every functional requirement demonstrably met.
- Test suite covers price-time priority, partial fills, market orders, cancels, modifies,
  and the obvious edge cases, and passes.
- A worked example (order stream to trades to final book) is documented and reproducible.
- Docs explain what the engine does, how to use it, and its limits.
- Determinism and quantity conservation are checked by tests, not asserted by hand.

## Deferred

Additional order types (IOC, FOK, stop), a latency benchmark harness, real market-data
ingestion, and multi-symbol support. Likely next steps, not requirements here.
