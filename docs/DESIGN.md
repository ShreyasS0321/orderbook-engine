# Design

This is the *how*. It records the data structures, the operating rules, and the edge
cases that took the most thought. Requirements (the *what*) are in `REQUIREMENTS.md`.

## Prices as integers

Floating point is banned everywhere in the engine. The usual reason applies: `0.1 + 0.2`
is not `0.3` in IEEE 754, and rounding drift in a matching engine turns into orders that
should have crossed but didn't, or fills at the wrong price.

Instead, prices are scaled by a fixed factor on the way in and stored as plain integers.
The scale factor is `PRICE_SCALE = 10**5`, so a price of `101.50` is carried internally as
`10150000`. Integer arithmetic is exact and, as a bonus, faster than float on the CPU.
Quantities are already whole units (shares), so they stay as ordinary integers and are not
scaled.

## The data structures

The engine avoids anything that needs an O(N) shift of elements. Everything below is
either O(1) or O(log N), and each structure exists to make one specific operation cheap.

- Order tracker, `order_id -> Order`. A single dictionary giving O(1) access to any resting
  order. This is what makes cancels and modifies fast: we never scan a queue looking for an
  order, we look it up directly.

- Price levels, `price -> deque`. A dictionary from a price to a `collections.deque` of the
  orders resting at that price. The deque gives O(1) `append` when an order arrives and O(1)
  `popleft` when the front order trades. Front of the deque is the oldest order, which is
  exactly the time priority we want.

- Best-price tracker, one heap per side. Sellers (asks) use a min-heap so the lowest ask is
  on top. Buyers (bids) use a max-heap, which Python's `heapq` doesn't provide directly, so
  bid prices are stored negated and a min-heap over the negatives behaves as a max-heap.
  Peeking the best price is O(1); inserting a new price level or removing an exhausted one is
  O(log N).

- Volume tracker, `price -> int`. A separate dictionary holding the live share count at each
  price. Keeping this running total means market-depth queries never have to iterate a deque
  to sum quantities, and it stays correct because it is updated at the moment an order's state
  changes.

## The BookSide seam

Notice that only a handful of operations actually depend on how prices are ordered: get the
best price, add an order at its level, drop a level once it empties, and read the top N levels
for depth. Everything else — the order tracker, tombstoning, the volume tracker, the matching
logic — is independent of that choice.

So those four operations live behind an interface, `BookSide`. The rest of the engine talks to
`BookSide` and never touches a heap directly. The first implementation, `HeapBookSide`, uses
the heap-plus-deque design above. A second, `SortedDictBookSide`, will use a
`sortedcontainers.SortedDict`, where the levels are always sorted and depth reads are trivial.
Both are exercised by the same test suite, which is the real proof that the seam is honest, and
a small benchmark compares them. The point is partly practical and partly to make the trade-off
between the two designs measurable rather than hand-waved.

## Who adjusts the volume

A `BookSide` tracks the live volume at each level, but it does not run the matching, so the two
have to agree on who subtracts what — otherwise the count drifts. The contract:

- A **partial fill** leaves the order resting with a smaller size. `OrderBook` mutates the
  order's quantity and calls `reduce_volume(price, filled)` for the amount that traded.
- A **full removal** pops the order off the front. `pop_best_order` itself subtracts the
  order's remaining quantity — except when the order is a tombstone, which already had its
  volume removed at cancel time. That exception is the "adjusted once" rule below, enforced in
  one place (`if not order.is_cancelled`).
- A **cancel** subtracts the order's remaining quantity via `reduce_volume` and flags the order.
  The later pop of that tombstone subtracts nothing.

The net effect is the invariant that every unit of volume is counted out exactly once, whether
it leaves by trading or by cancellation.

## Operating rules

Market orders. A market order never rests. A market buy repeatedly takes the best ask, popping
from the front of that price's deque until the order is filled or the ask side is empty. Any
quantity left over when the book runs dry is simply dropped — fill what you can, kill the rest.

Cancellations, done lazily. We never walk a deque to delete an order. A cancel looks the order
up in the order tracker in O(1), sets `is_cancelled = True`, and subtracts its quantity from the
volume tracker straight away so depth stays accurate. The order object is left sitting in its
deque as a tombstone. Later, when matching reaches it, the flag is seen and the order is discarded
in O(1). The important invariant here: the volume is adjusted once, at cancel time. When the dead
order is finally popped during a sweep, nothing is subtracted again.

Modifications, and why they aren't symmetric. Decreasing an order's quantity keeps its position
and its timestamp; only the size changes, updated in place. Increasing the quantity or changing
the price is a cancel-and-replace: the old order is tombstoned and a fresh order goes to the back
of its price queue with a new timestamp. This isn't arbitrary. If a size increase kept your place
in line, you could rest one share at the front of the queue, hold that position cheaply, and inflate
your size the moment you wanted to trade — jumping everyone who queued honestly behind you. Sending
increases to the back removes that game.

## Edge cases worth calling out

Ghost levels. Because cancels are lazy, a price level's deque can end up full of nothing but
cancelled orders while the price itself is still sitting in the heap. The matcher handles this
without any special case: when it works through a level it pops and discards the dead orders, and
once the deque is empty it `heappop`s the price out of the heap and moves to the next best price.
Reads of the best price do the same cleanup — skip any dead level on top before reporting — so
best bid and best ask are amortised O(1) rather than strictly O(1).

One consequence to be honest about: a cancelled level deep in the book, one the matcher never
reaches, stays in the heap until something trades through it. Over a long run these accumulate.
This is a known cost of the heap design and one of the things the `SortedDict` backend avoids,
since it can delete a level in place the moment it empties.

Market depth. A client asking for the top five levels and their volumes can't have us popping the
heap (that would destroy it) or summing deques (too slow). With the heap backend we read the top
prices non-destructively with `heapq.nsmallest`, cross-reference each against the volume tracker,
skip any level whose volume is zero, and stop once five live levels are collected. Because ghosts
have to be skipped, this means pulling more than five candidates when some are dead, and `nsmallest`
is recomputed per call — another place the `SortedDict` backend is simply cheaper, and another
reason the comparison is worth measuring.

## Deferred

IOC and FOK orders, stop orders, real market-data ingestion, and multi-symbol support are out of
scope for now. The design leaves room for them but doesn't build them.
