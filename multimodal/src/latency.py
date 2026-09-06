"""Warm local wall-clock latency, with measured scope stated in every output."""
from time import perf_counter_ns

import numpy as np


def latency_summary(samples):
    samples = np.asarray(samples, dtype=np.float64)
    if not len(samples) or not np.isfinite(samples).all() or np.any(samples < 0):
        raise ValueError("Latency requires finite nonnegative observations")
    return {"samples": len(samples), "p50_ms": float(np.percentile(samples, 50)),
            "p95_ms": float(np.percentile(samples, 95)), "mean_ms": float(samples.mean())}


def measure(function, inputs, repeats=3, warmups=5):
    if not inputs or repeats < 1:
        raise ValueError("Latency population and repeats must be positive")
    for i in range(warmups):
        function(inputs[i % len(inputs)])
    samples = []
    for _ in range(repeats):
        for item in inputs:
            started = perf_counter_ns()
            function(item)
            samples.append((perf_counter_ns() - started) / 1e6)
    return {**latency_summary(samples), "queries": len(inputs), "repeats": repeats,
            "warmups": warmups}, samples
