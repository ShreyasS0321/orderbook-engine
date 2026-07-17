"""Measurement primitives: timing, percentile stats, environment capture.

Per-operation latencies are recorded into a pre-allocated array and reduced to
exact percentiles. We run offline and can keep every sample, so exact beats an
approximate histogram.
"""

import gc
import platform
import subprocess
import time
from collections.abc import Callable

import numpy as np
import psutil


def environment() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "git_commit": _git_commit(),
    }


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def pin_cpu() -> bool:
    """Pin this process to a single core. Returns False if the OS refuses."""
    try:
        proc = psutil.Process()
        proc.cpu_affinity([proc.cpu_affinity()[0]])
        return True
    except (AttributeError, OSError, psutil.Error):
        return False


def measure(
    op: Callable[[int], object],
    count: int,
    warmup: int = 10_000,
    disable_gc: bool = True,
) -> np.ndarray:
    """Time ``op(i)`` for ``count`` iterations; return per-call latency in ns.

    ``op`` receives a monotonic index so it can pull pre-staged, non-repeating
    data. The first ``warmup`` calls are untimed. GC is off during the timed
    region by default; pass ``disable_gc=False`` to measure its impact.
    """
    perf = time.perf_counter_ns
    for i in range(warmup):
        op(i)

    samples = np.empty(count, dtype=np.int64)
    gc_was_enabled = gc.isenabled()
    if disable_gc:
        gc.disable()
    try:
        for j in range(count):
            i = warmup + j
            t0 = perf()
            op(i)
            t1 = perf()
            samples[j] = t1 - t0
    finally:
        if disable_gc and gc_was_enabled:
            gc.enable()
    return samples


def timer_overhead(count: int = 100_000) -> np.ndarray:
    """Latency of two back-to-back clock reads: the measurement noise floor."""
    perf = time.perf_counter_ns
    samples = np.empty(count, dtype=np.int64)
    for j in range(count):
        t0 = perf()
        t1 = perf()
        samples[j] = t1 - t0
    return samples


def summarize(samples: np.ndarray) -> dict[str, float]:
    p50, p90, p99, p999 = np.percentile(samples, [50, 90, 99, 99.9])
    return {
        "count": float(samples.size),
        "mean": float(samples.mean()),
        "p50": float(p50),
        "p90": float(p90),
        "p99": float(p99),
        "p99.9": float(p999),
        "max": float(samples.max()),
    }


if __name__ == "__main__":
    print("environment:", environment())
    print("cpu pinned:", pin_cpu())
    print("timer overhead (ns):", summarize(timer_overhead()))
