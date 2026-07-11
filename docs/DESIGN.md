# Design

The *how*. Data structures, operating rules, and the edge cases that needed thought.
Requirements (the *what*) are in `REQUIREMENTS.md`.

## Prices as integers

No floats anywhere in the engine. `0.1 + 0.2 != 0.3` in IEEE 754, and that rounding drift
shows up as orders that should have crossed but didn't, or fills at the wrong price.

Prices are scaled by a fixed factor on input and stored as `int`. `PRICE_SCALE = 10**5`,
so `101.50` is held as `10150000`. Integer compares and adds are exact, which is the whole
point. Quantities are already whole shares, so they stay plain ints and are not scaled.

## Data structures

No operation may need an O(N) shift. Each structure below exists to make one thing cheap:

- `order_id -> Order` dict. O(1) lookup of any resting order. Cancel and modify use this
  instead of scanning a queue.
- `price -> deque` dict. The orders resting at a price, oldest at the front. `append` on
  arrival and `popleft` on a fill are both O(1). Front-of-deque = time priority.
- One heap per side for the best price. Asks: min-heap, lowest on top. Bids: max-heap,
  which `heapq` doesn't provide, so bid prices are stored negated and a min-heap over the
  negatives gives the highest price on top. Peek is O(1); adding or removing a level is
  O(log N).
- `price -> int` volume dict. Live share count per level. Depth queries read this instead
  of summing a deque; it is updated whenever an order's state changes.

## The BookSide seam

Only four operations depend on how prices are ordered: best price, add an order at its
level, drop a level when it empties, read the top N levels. The order tracker, tombstoning,
volume tracking, and matching don't care about the ordering structure.

So those four sit behind a `BookSide` interface and the rest of the engine never touches a
heap directly. `HeapBookSide` is the heap-plus-deque design above. `SortedDictBookSide`
(planned) uses `sortedcontainers.SortedDict`, where levels stay sorted and depth reads are
trivial. Both run against the same test suite, and a benchmark compares them.

## Who adjusts the volume

A `BookSide` tracks volume but doesn't run the matching, so the two must agree on who
subtracts what or the count drifts.

- Partial fill: the order stays, smaller. `OrderBook` reduces its quantity and calls
  `reduce_volume(price, filled)`.
- Full removal: `pop_best_order` subtracts the order's remaining quantity itself. Exception:
  a tombstone already lost its volume at cancel time, so pop skips it (`if not
  order.is_cancelled`).
- Cancel: `reduce_volume(remaining)` plus flag the order. The later pop of that tombstone
  subtracts nothing.

Net: every unit is counted out exactly once, whether it leaves by trade or by cancel.

## Operating rules

**Market orders.** Never rest. A market buy repeatedly takes the best ask, popping from the
front until filled or the ask side is empty. Any unfilled remainder is dropped.

**Cancels (lazy).** No deque is ever scanned to delete an order. Cancel looks the order up
in O(1), sets `is_cancelled = True`, and subtracts its quantity from the volume tracker so
depth stays right. The order stays in its deque as a tombstone. The matcher discards it in
O(1) when it reaches it. Volume is adjusted once, at cancel time (see above).

**Modify.** Decreasing quantity keeps queue position and timestamp; the size changes in
place. Increasing quantity or changing price is cancel-and-replace: tombstone the old order,
add a fresh one at the back of the queue with a new timestamp.

The asymmetry is deliberate. If a size increase kept your place in line, you could rest one
share at the front, hold that position cheaply, then inflate the size right before trading,
jumping everyone who queued honestly behind you. Sending increases to the back closes that.

## Edge cases

**Ghost levels.** Because cancels are lazy, a level's deque can hold only cancelled orders
while its price still sits in the heap. No special case: the matcher pops and discards the
dead orders as it goes, and `heappop`s the price once the deque empties. Best-price reads do
the same cleanup first, so best bid/ask are amortised O(1), not strictly O(1).

A cancelled level deep in the book, one the matcher never reaches, stays in the heap until
something trades through it, so these accumulate over a long run. Known cost of the heap
design; `SortedDict` avoids it by deleting a level in place the moment it empties.

**Market depth.** Reading the top N levels can't pop the heap (destroys it) or sum deques
(too slow). The heap backend reads top prices non-destructively with `heapq.nsmallest`,
checks each against the volume tracker, skips zero-volume levels, and stops at N live ones.
Skipping ghosts means pulling more than N candidates when some are dead, and `nsmallest`
recomputes per call. `SortedDict` is cheaper here, which the benchmark should show.

## Deferred

IOC/FOK, stop orders, real market-data ingestion, and multi-symbol support are out of scope.
The design leaves room for them.
