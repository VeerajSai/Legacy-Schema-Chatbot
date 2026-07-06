"""Seeds a few-shot bank from eval/golden_set.jsonl (owned by a parallel
agent). Must tolerate that file being absent or still mid-write: any failure
here just yields an empty bank, never a crash."""
from __future__ import annotations

import json
from pathlib import Path

from config.settings import FEWSHOT_BANK_PATH, GOLDEN_SET_PATH


def build_fewshot_bank(golden_path=GOLDEN_SET_PATH, out_path=FEWSHOT_BANK_PATH) -> list[dict]:
    bank: list[dict] = []
    path = Path(golden_path)
    if path.exists():
        try:
            lines = path.read_text().splitlines()
        except OSError:
            lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            question, sql = rec.get("question"), rec.get("sql")
            if question and sql:
                bank.append({
                    "question": question,
                    "sql": sql,
                    "tables_used": rec.get("tables_used", rec.get("tables", [])),
                })

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bank, indent=2))
    return bank
