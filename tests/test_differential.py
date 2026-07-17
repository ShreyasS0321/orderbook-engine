"""Differential test: both backends must produce identical results.

Replaying the same command stream through OrderBook on each backend must yield
identical trades and an identical final book. This is what makes any latency
comparison between them apples-to-apples.
"""

import pytest

from benchmarks.workload import generate, replay
from orderbook.book import OrderBook
from orderbook.book_side import HeapBookSide, SortedDictBookSide


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 99])
def test_backends_are_observationally_identical(seed: int) -> None:
    commands = generate(5000, seed=seed)

    heap = OrderBook(HeapBookSide)
    sorted_dict = OrderBook(SortedDictBookSide)

    heap_results = replay(commands, heap)
    sorted_dict_results = replay(commands, sorted_dict)

    assert heap_results == sorted_dict_results
    assert heap.depth(1000) == sorted_dict.depth(1000)
