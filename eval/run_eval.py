"""Runnable as `python -m eval.run_eval`.

Calls the pipeline end to end for every resolved golden question and reports
execution accuracy (overall + per-difficulty) and table-recall@k, per doc
section 6. Until the offline catalog + online pipeline are fully wired up
(and ANTHROPIC_API_KEY is set), most/all questions will fail -- that's
expected; each failure is caught and counted as a miss so the report always
completes and is useful as a diagnostic the moment things land.
"""
from __future__ import annotations

import json
from collections import defaultdict

from config.settings import GOLDEN_SET_RESOLVED_PATH, TABLE_RECALL_TARGET
from eval.metrics import execution_match


def _load_golden():
    if not GOLDEN_SET_RESOLVED_PATH.exists():
        raise SystemExit(
            f"{GOLDEN_SET_RESOLVED_PATH} not found -- run `python -m eval.build_golden_set` first."
        )
    with open(GOLDEN_SET_RESOLVED_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run() -> dict:
    try:
        from pipeline.orchestrator import answer_question  # may not exist/work yet
    except Exception as e:  # noqa: BLE001 -- missing/broken orchestrator must not crash the report
        answer_question = None
        print(f"pipeline.orchestrator.answer_question unavailable ({type(e).__name__}: {e}); "
              f"every question below counts as a miss.\n")

    golden = _load_golden()

    per_difficulty_total = defaultdict(int)
    per_difficulty_correct = defaultdict(int)
    table_recall_hits = 0
    n_errors = 0

    for rec in golden:
        difficulty = rec["difficulty"]
        per_difficulty_total[difficulty] += 1
        expected_rows = [tuple(row) for row in rec["expected_rows"]]
        expected_tables = set(rec["expected_tables"])

        if answer_question is None:
            n_errors += 1
            continue

        try:
            ctx = answer_question(rec["question"], user_id="eval", role="admin")

            generated_rows = ctx.execution.rows if ctx.execution and ctx.execution.rows else []
            if execution_match(expected_rows, generated_rows):
                per_difficulty_correct[difficulty] += 1

            all_tables = set(getattr(ctx.graph, "all_tables", []) or []) if ctx.graph else set()
            if expected_tables <= all_tables:
                table_recall_hits += 1
        except Exception as e:  # noqa: BLE001 -- one bad question must never kill the report
            n_errors += 1
            print(f"[{rec['id']}] ERROR: {type(e).__name__}: {e}")

    n_total = len(golden)
    n_correct = sum(per_difficulty_correct.values())
    table_recall = table_recall_hits / n_total if n_total else 0.0

    print("\n=== Execution accuracy ===")
    print(f"Overall: {n_correct}/{n_total} ({100 * n_correct / n_total:.1f}%)" if n_total else "no questions")
    for diff in sorted(per_difficulty_total):
        t, c = per_difficulty_total[diff], per_difficulty_correct[diff]
        print(f"  {diff:28s} {c}/{t} ({100 * c / t:.1f}%)")

    print("\n=== Table recall@k ===")
    print(f"{table_recall_hits}/{n_total} ({100 * table_recall:.1f}%)"
          + (" -- BELOW TARGET" if table_recall < TABLE_RECALL_TARGET else " -- meets target")
          + f" (target {TABLE_RECALL_TARGET * 100:.0f}%)")

    print(f"\nErrors/exceptions: {n_errors}/{n_total}")

    return {
        "n_total": n_total,
        "n_correct": n_correct,
        "execution_accuracy": n_correct / n_total if n_total else 0.0,
        "table_recall": table_recall,
        "n_errors": n_errors,
        "per_difficulty": {
            d: per_difficulty_correct[d] / per_difficulty_total[d]
            for d in per_difficulty_total
        },
    }


if __name__ == "__main__":
    run()
