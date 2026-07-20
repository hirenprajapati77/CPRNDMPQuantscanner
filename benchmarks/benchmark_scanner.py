"""
NDMP OS v6.0 - Performance & Latency Benchmark Suite
Monitors both Micro-benchmarks (CPR calculation) and End-to-End pipeline benchmarks.
"""

import time
import tracemalloc
from typing import List, Dict
import pandas as pd
import numpy as np
from ndmp_research.features.cpr_feature import CPRFeature
from ndmp_research.features.vwap_feature import VWAPFeature
from ndmp_research.feature_registry import FeatureRegistry


def run_benchmark_suite(num_iterations: int = 50, warmups: int = 5) -> None:
    """Run full benchmark suite with statistical logging and peak memory auditing."""
    print(f"[BENCHMARK] Initializing benchmark: {num_iterations} runs, discarding first {warmups} warmups...")
    
    # Enable memory tracing
    tracemalloc.start()
    
    # 1. CPR Micro Benchmark Data Setup
    cpr_plugin = CPRFeature()
    num_stocks = 180
    num_rows = 1000
    dates = pd.date_range("2026-01-01", periods=num_rows, freq="D")
    highs = np.random.uniform(100, 200, size=(num_rows,))
    lows = highs - np.random.uniform(1, 10, size=(num_rows,))
    closes = lows + np.random.uniform(0.5, 5, size=(num_rows,))
    df_micro = pd.DataFrame({"high": highs, "low": lows, "close": closes}, index=dates)

    # 2. E2E Benchmark Setup
    registry = FeatureRegistry(registry_dir="ndmp_research/registry")
    registry.discover_manifests()
    registry.register_feature_instance(CPRFeature())
    registry.register_feature_instance(VWAPFeature())
    vwap = closes - 0.5
    df_e2e = pd.DataFrame({"high": highs, "low": lows, "close": closes, "vwap": vwap}, index=dates)

    micro_times = []
    e2e_times = []

    # Iteration loop
    for i in range(num_iterations):
        # Micro run
        start = time.perf_counter()
        for _ in range(num_stocks):
            _ = cpr_plugin.calculate(df_micro)
        t_micro = (time.perf_counter() - start) * 1000.0
        
        # E2E run
        start = time.perf_counter()
        for _ in range(num_stocks):
            _ = registry.calculate_all(df_e2e)
        t_e2e = (time.perf_counter() - start) * 1000.0

        if i >= warmups:
            micro_times.append(t_micro)
            e2e_times.append(t_e2e)

    # Calculate Peak Memory
    current, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak_bytes / (1024.0 * 1024.0)

    # Compute Statistics
    def get_stats(times: List[float]) -> Dict[str, float]:
        arr = np.array(times)
        return {
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "p95": float(np.percentile(arr, 95)),
            "std": float(np.std(arr))
        }

    micro_stats = get_stats(micro_times)
    e2e_stats = get_stats(e2e_times)

    print("\n" + "=" * 80)
    print("NDMP OS v6.0 PERFORMANCE BENCHMARK REPORT")
    print("=" * 80)
    print(f"{'Metric':<15} | {'Micro CPR (ms)':<20} | {'E2E Ingestion + Compute (ms)':<30}")
    print("-" * 80)
    print(f"{'Mean':<15} | {micro_stats['mean']:<20.2f} | {e2e_stats['mean']:<30.2f}")
    print(f"{'Median':<15} | {micro_stats['median']:<20.2f} | {e2e_stats['median']:<30.2f}")
    print(f"{'P95':<15} | {micro_stats['p95']:<20.2f} | {e2e_stats['p95']:<30.2f}")
    print(f"{'Std Dev':<15} | {micro_stats['std']:<20.2f} | {e2e_stats['std']:<30.2f}")
    print("-" * 80)
    print(f"Peak Memory Usage: {peak_mb:.2f} MB (Performance Budget: < 512.00 MB)")
    print("=" * 80 + "\n")

    # Assertions
    assert micro_stats["p95"] < 2500.0, "Micro benchmark P95 budget exceeded!"
    assert e2e_stats["p95"] < 5000.0, "End-to-End benchmark P95 budget exceeded!"
    assert peak_mb < 512.0, "Peak memory budget exceeded!"
    print("[BENCHMARK PASS] All benchmarks within performance and memory budgets.")


if __name__ == "__main__":
    run_benchmark_suite()
