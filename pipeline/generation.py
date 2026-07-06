"""Stage 7: SQL generation, strong model only (doc section 4 stage 7)."""
from __future__ import annotations

import re

from contracts.llm_client import LLMClient

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.S | re.I)


def generate_sql(system: str, user: str, llm: LLMClient) -> str:
    resp = llm.call_strong(system, user)
    text = resp.text.strip()
    match = _FENCE.search(text)
    sql = match.group(1) if match else text
    return sql.strip().rstrip(";").strip()
