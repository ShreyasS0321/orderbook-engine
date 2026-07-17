# Performance: book-side backend comparison

Two `BookSide` backends implement the same interface: `HeapBookSide` (a binary heap
of prices plus per-price deques) and `SortedDictBookSide` (a `sortedcontainers.SortedDict`
of prices to deques). This measures where each one wins, per operation.

The short version: the heap is faster for point operations (add, pop, best price); the
sorted dict is ~4x faster for depth queries. Which one to pick depends on the read/write
mix of whatever sits on top.

## Method

- **Micro-benchmark**: each `BookSide` operation timed in isolation against a book
  pre-filled to ~20k resting orders, so it runs at a realistic depth rather than from
  empty.
- **Two metrics**: per-operation **latency** (each call timed with `perf_counter_ns`
  into a pre-allocated array, exact percentiles via `numpy.percentile`) and **throughput**
  (a batched loop, which amortises clock overhead and gives an accurate mean).
- **1,000,000 measured operations** per case (after 10k untimed warmup) — enough for a
  stable p99.9.
- **Fairness**: both backends implement identical price-time-priority semantics, and a
  differential test (`tests/test_differential.py`) replays the same command stream through
  each and asserts identical trades and identical final book. If they diverged, this
  comparison would be meaningless.
- **Hygiene**: process pinned to one core, GC disabled during the timed region, warmup
  discarded.

### Environment

| | |
|---|---|
| CPython | 3.12.3 |
| OS | Linux 6.8.0 |
| CPU | x86_64 |
| commit | bccff00 |

Timer overhead (two back-to-back clock reads) on this machine: p50 **50 ns**, p99 61 ns.
So the ~220 ns point-operation numbers below include roughly 50 ns of measurement cost;
the true operation cost is a bit lower. The comparison between backends is unaffected,
since the overhead is identical for both.

Raw results: [`perf/book_side_linux.json`](perf/book_side_linux.json).

## Results

Latency in nanoseconds; throughput in millions of ops/sec. Faster is bold.

### add_order

| backend | p50 | p90 | p99 | p99.9 | max | Mops/s |
|---|---|---|---|---|---|---|
| heap | **221** | 251 | 401 | 1894 | 30896 | **5.06** |
| sorted_dict | 240 | 281 | 471 | 1723 | 21599 | 4.65 |

### pop_best_order

| backend | p50 | p90 | p99 | p99.9 | max | Mops/s |
|---|---|---|---|---|---|---|
| heap | **602** | 912 | 1162 | 2054 | 125107 | **1.61** |
| sorted_dict | 692 | 1012 | 1272 | 3106 | 131969 | 1.43 |

### get_best_price

| backend | p50 | p90 | p99 | p99.9 | max | Mops/s |
|---|---|---|---|---|---|---|
| heap | **221** | 251 | 391 | 451 | 128803 | **5.13** |
| sorted_dict | 321 | 351 | 470 | 662 | 20237 | 3.49 |

### get_top_levels(10)

| backend | p50 | p90 | p99 | p99.9 | max | Mops/s |
|---|---|---|---|---|---|---|
| heap | 3917 | 3987 | 6863 | 9818 | 128393 | 0.26 |
| sorted_dict | **1001** | 1042 | 1412 | 3256 | 135084 | **1.05** |

## Why

**Point operations favour the heap.** `get_best_price` is the clearest case: the heap
reads `heap[0]` in O(1), while `SortedDict.peekitem(index)` is O(log n) because it locates
a key by rank in the sorted order. That difference shows up directly: 221 ns vs 321 ns.
`add_order` and `pop_best_order` are closer, but the heap's `heappush`/`heappop` still
edge out the sorted dict's tree insertion and deletion.

**Depth queries favour the sorted dict, by ~4x.** `get_top_levels(10)` has to return the
best ten price levels in order. The sorted dict is already ordered, so it walks the first
ten keys — O(k). The heap is only partially ordered, so it has no way to read the top ten
without touching every level: the current implementation sorts all resting price levels on
each call. With ~200 levels in the book that is O(M log M) of avoidable work per query,
which is why the heap sits at 3917 ns against the sorted dict's 1001 ns.

**Tails.** p99.9 stays in the low microseconds for every case; the `max` values (30–135 µs)
are OS scheduling and allocator hiccups that land even with the process pinned, not
properties of the data structures. p99.9 is the honest tail number here, not max.

## Conclusion

There is no single winner, and that is the useful result:

- A consumer dominated by **submit / cancel / best-price** churn (a matching hot path)
  should use the **heap**.
- A consumer dominated by **depth snapshots** (L2 market-data dissemination, anything that
  repeatedly reads the top N levels) should use the **sorted dict**.

Because both sit behind the same `BookSide` interface, the choice is a one-line swap and
is validated by the same test suite.

## Limitations and next steps

- The heap's depth cost is partly an implementation choice: sorting all levels each call.
  Using `heapq.nsmallest(k)` would make it O(M log k) instead of O(M log M), narrowing but
  not closing the gap — the heap still has to examine every level, while the sorted dict
  does not.
- Single machine, single run. Numbers are for relative comparison, not absolute claims.
- Latency here is per-call service time, not response time under sustained load, so
  coordinated omission does not apply; a load test would be a separate measurement.
- Next backends to add to this comparison: an array-indexed price ladder, and a
  Cython/C++ hot path, run through this same harness.
