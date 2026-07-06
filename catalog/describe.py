"""One-time LLM description generation per table (doc's highest-ROI catalog
investment: legacy names like `ord_dtl_2` are meaningless on their own).
Cached to DESCRIBE_CACHE_PATH so re-running build_catalog doesn't re-call the
LLM. Works with zero API key: StubLLMClient never produces useful prose, so
that path is short-circuited to a deterministic fallback instead of being
sent through the stub.
"""
from __future__ import annotations

import json
from pathlib import Path

from config.settings import DESCRIBE_CACHE_PATH
from contracts.db import get_connection
from contracts.llm_client import StubLLMClient, get_llm_client

SAMPLE_ROWS = 3


def _load_cache(path) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _fallback_description(table: str, module: str, columns: list[dict]) -> str:
    col_names = ", ".join(c["name"] for c in columns)
    return f"Table '{table}' in the {module} module with columns: {col_names}."


def describe_tables(crawled: dict, modules: dict[str, str], cache_path=DESCRIBE_CACHE_PATH) -> dict[str, str]:
    """modules: {table: module_name}. Returns {table: description}, persisted to cache_path."""
    cache = _load_cache(cache_path)
    client = get_llm_client()
    use_llm = not isinstance(client, StubLLMClient)

    conn = get_connection(read_only=True) if use_llm else None
    try:
        for table, info in crawled.items():
            if table in cache:
                continue
            module = modules.get(table, "unknown")
            columns = info["columns"]
            if not use_llm:
                cache[table] = _fallback_description(table, module, columns)
                continue

            col_line = ", ".join(f"{c['name']} ({c['dtype']})" for c in columns)
            samples = conn.execute(f"SELECT * FROM {table} LIMIT {SAMPLE_ROWS}").fetchall()
            sample_line = "\n".join(str(tuple(r)) for r in samples) or "(no rows)"
            system = "You write a single, concise, one-sentence description of a database table for a data catalog."
            user = (
                f"Table: {table}\nModule: {module}\nColumns: {col_line}\nSample rows:\n{sample_line}\n"
                "Write one sentence describing what this table stores."
            )
            resp = client.call_cheap(system, user, max_tokens=100)
            text = resp.text.strip()
            cache[table] = text if text else _fallback_description(table, module, columns)
    finally:
        if conn is not None:
            conn.close()

    p = Path(cache_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, indent=2))
    return cache
