# orderbook-engine

An in-memory limit order book matching engine in Python: the matching core an exchange
runs on. It takes a stream of orders, matches them by price-time priority, emits trades,
and exposes top-of-book and depth views.

Work in progress. See [`docs/`](docs/) for [requirements](docs/REQUIREMENTS.md) and
[design](docs/DESIGN.md); a usage guide and benchmarks land once the engine is complete.

## Status

- Done: core types, the `BookSide` storage layer (heap backend), limit-order matching,
  order cancellation. Tested, linted, type-checked in CI.
- Next: market orders, modify, book reporting (best bid/ask, spread, depth).

## License

MIT
