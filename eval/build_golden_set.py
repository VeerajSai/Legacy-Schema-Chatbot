"""Runnable as `python -m eval.build_golden_set`.

Executes every SQL statement in golden_set.jsonl against the real data/legacy.db
(read-only), canonicalizes the result, and writes golden_set_resolved.jsonl with
the resolved rows attached -- so run_eval.py never has to re-derive "truth" and
never touches the DB with write intent.
"""
from __future__ import annotations

import json

from config.settings import GOLDEN_SET_PATH, GOLDEN_SET_RESOLVED_PATH
from contracts.db import get_connection
from eval.metrics import canonicalize


def build() -> None:
    conn = get_connection(read_only=True)
    try:
        cur = conn.cursor()
        resolved = []
        for lineno, line in enumerate(open(GOLDEN_SET_PATH, encoding="utf-8"), start=1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            try:
                cur.execute(rec["sql"])
                rows = [tuple(r) for r in cur.fetchall()]
            except Exception as e:
                raise RuntimeError(f"golden_set.jsonl line {lineno} ({rec['id']}) failed: {e}\nSQL: {rec['sql']}") from e
            canon_rows = canonicalize(rows)
            resolved.append({
                **rec,
                "expected_row_count": len(canon_rows),
                "expected_rows": canon_rows,
            })
    finally:
        conn.close()

    GOLDEN_SET_RESOLVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GOLDEN_SET_RESOLVED_PATH, "w", encoding="utf-8") as f:
        for rec in resolved:
            f.write(json.dumps(rec) + "\n")

    print(f"Resolved {len(resolved)} golden questions -> {GOLDEN_SET_RESOLVED_PATH}")


if __name__ == "__main__":
    build()
