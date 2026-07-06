"""Shared canonicalization for execution-accuracy comparisons, plus a CLI to
summarize the pipeline's JSONL log (doc section 6: execution match, not exact
SQL match; doc section 7: cache hit rate, tokens/query, latency, error rate).
"""
from __future__ import annotations

import json
import statistics
from collections import Counter

from config.settings import PIPELINE_LOG_PATH

# ponytail: 4dp is plenty for money/qty aggregates in this synthetic dataset;
# bump if a real deployment needs tighter float comparisons.
FLOAT_ROUND_DP = 4


def _canon_value(v) -> str:
    if isinstance(v, float):
        return str(round(v, FLOAT_ROUND_DP))
    return str(v)


def canonicalize(rows: list[tuple]) -> list[tuple]:
    """Cast every value to str (rounding floats first), sort rows. Column order
    and row order are irrelevant to correctness, so both are normalized away."""
    canon = [tuple(_canon_value(v) for v in row) for row in rows]
    return sorted(canon)


def execution_match(golden_rows, generated_rows) -> bool:
    """Multiset compare (Counter), not set compare, so duplicate rows from a
    join fan-out bug are caught instead of silently deduped."""
    return Counter(canonicalize(golden_rows)) == Counter(canonicalize(generated_rows))


def summarize_log(log_path=PIPELINE_LOG_PATH) -> dict:
    """Reads the JSONL pipeline log (one event/query per line) and returns
    aggregate metrics. Returns a dict with a `note` key and zeroed fields if
    the log doesn't exist yet (no queries have run)."""
    if not log_path.exists():
        return {
            "note": f"no log found at {log_path}; run some queries first",
            "n_events": 0,
            "cache_hit_rate_by_tier": {},
            "tokens_per_query_mean": None,
            "latency_ms_p50": None,
            "latency_ms_p95": None,
            "error_rate": None,
        }

    events = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    n = len(events)
    if n == 0:
        return {
            "note": "log exists but has no valid events",
            "n_events": 0,
            "cache_hit_rate_by_tier": {},
            "tokens_per_query_mean": None,
            "latency_ms_p50": None,
            "latency_ms_p95": None,
            "error_rate": None,
        }

    cache_hits = Counter(e.get("cache_hit") for e in events)
    cache_hit_rate_by_tier = {
        str(tier): count / n for tier, count in cache_hits.items() if tier
    }

    token_totals = [
        sum(e["tokens_used"].values())
        for e in events
        if isinstance(e.get("tokens_used"), dict) and e["tokens_used"]
    ]
    tokens_per_query_mean = statistics.mean(token_totals) if token_totals else None

    latencies = [e["latency_ms"] for e in events if isinstance(e.get("latency_ms"), (int, float))]
    if not latencies:
        # fall back to summed stage_timings_ms if per-event latency wasn't logged directly
        latencies = [
            sum(e["stage_timings_ms"].values())
            for e in events
            if isinstance(e.get("stage_timings_ms"), dict) and e["stage_timings_ms"]
        ]
    latencies.sort()
    p50 = statistics.median(latencies) if latencies else None
    p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else None

    errors = sum(1 for e in events if e.get("error") or e.get("blocked_reason"))
    error_rate = errors / n

    return {
        "n_events": n,
        "cache_hit_rate_by_tier": cache_hit_rate_by_tier,
        "tokens_per_query_mean": tokens_per_query_mean,
        "latency_ms_p50": p50,
        "latency_ms_p95": p95,
        "error_rate": error_rate,
    }


if __name__ == "__main__":
    print(json.dumps(summarize_log(), indent=2, default=str))
