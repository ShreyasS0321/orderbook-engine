"""Micro-benchmark: race the BookSide backends per operation.

Each operation is set up against a pre-filled book so it runs at a realistic
depth, then measured two ways: latency percentiles (per-op) and throughput
(batched). Results are printed and written to benchmarks/results/ as JSON.

Run:  python -m benchmarks.bench_book_side --count 1000000
"""

import argparse
import json
import random
from collections.abc import Callable
from pathlib import Path

from orderbook.book_side import BookSide, HeapBookSide, SortedDictBookSide
from orderbook.types import Order, OrderType, Side

from .harness import environment, measure, pin_cpu, summarize, throughput, timer_overhead

BACKENDS: dict[str, type[BookSide]] = {
    "heap": HeapBookSide,
    "sorted_dict": SortedDictBookSide,
}

PREFILL = 20_000


def make_orders(n: int, seed: int, mid: int = 100_000, max_offset: int = 200) -> list[Order]:
    rng = random.Random(seed)
    orders = []
    for i in range(1, n + 1):
        offset = min(int(rng.expovariate(0.05)), max_offset)
        orders.append(
            Order(
                order_id=i,
                side=Side.SELL,
                quantity=rng.randint(1, 100),
                timestamp=i,
                order_type=OrderType.LIMIT,
                price=mid + offset,
            )
        )
    return orders


def _prefill(cls: type[BookSide], n: int, seed: int) -> BookSide:
    book = cls(Side.SELL)
    for order in make_orders(n, seed=seed):
        book.add_order(order)
    return book


# Each setup returns a zero-cost-per-call op closed over pre-staged state.

def setup_add(cls: type[BookSide], total: int) -> Callable[[int], object]:
    book = cls(Side.SELL)
    orders = make_orders(total, seed=1)
    return lambda i: book.add_order(orders[i])


def setup_pop(cls: type[BookSide], total: int) -> Callable[[int], object]:
    book = _prefill(cls, total, seed=2)
    return lambda i: book.pop_best_order()


def setup_best_price(cls: type[BookSide], total: int) -> Callable[[int], object]:
    book = _prefill(cls, PREFILL, seed=3)
    return lambda i: book.get_best_price()


def setup_depth(cls: type[BookSide], total: int) -> Callable[[int], object]:
    book = _prefill(cls, PREFILL, seed=4)
    return lambda i: book.get_top_levels(10)


SETUPS: dict[str, Callable[[type[BookSide], int], Callable[[int], object]]] = {
    "add_order": setup_add,
    "pop_best_order": setup_pop,
    "get_best_price": setup_best_price,
    "get_top_levels_10": setup_depth,
}


def run(count: int, warmup: int) -> dict:
    total = warmup + count
    results: dict = {
        "environment": environment(),
        "cpu_pinned": pin_cpu(),
        "config": {"count": count, "warmup": warmup, "prefill": PREFILL},
        "timer_overhead_ns": summarize(timer_overhead()),
        "backends": {},
    }

    for backend_name, cls in BACKENDS.items():
        per_op: dict = {}
        for op_name, setup in SETUPS.items():
            latency = summarize(measure(setup(cls, total), count, warmup))
            ops_per_s = throughput(setup(cls, total), count, warmup)
            per_op[op_name] = {"latency_ns": latency, "throughput_ops_s": ops_per_s}
        results["backends"][backend_name] = per_op

    return results


def print_table(results: dict) -> None:
    ops = list(SETUPS)
    for op_name in ops:
        print(f"\n{op_name}")
        print(f"{'backend':<14}{'p50':>8}{'p99':>8}{'p99.9':>9}{'max':>10}{'Mops/s':>10}")
        for backend_name in BACKENDS:
            stats = results["backends"][backend_name][op_name]
            lat = stats["latency_ns"]
            mops = stats["throughput_ops_s"] / 1e6
            print(
                f"{backend_name:<14}{lat['p50']:>8.0f}{lat['p99']:>8.0f}"
                f"{lat['p99.9']:>9.0f}{lat['max']:>10.0f}{mops:>10.2f}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="BookSide micro-benchmark")
    parser.add_argument("--count", type=int, default=200_000, help="measured ops per case")
    parser.add_argument("--warmup", type=int, default=10_000, help="untimed warmup ops")
    parser.add_argument("--out", type=Path, default=None, help="JSON output path")
    args = parser.parse_args()

    results = run(args.count, args.warmup)
    print_table(results)

    env = results["environment"]
    out = args.out or (
        Path(__file__).parent
        / "results"
        / f"book_side_{env['implementation']}_{env['system'].split()[0]}_{env['git_commit']}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
