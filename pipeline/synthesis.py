"""Stage 10: answer synthesis, cheap model (doc section 4 stage 10)."""
from __future__ import annotations

from contracts.llm_client import LLMClient
from contracts.types import PipelineContext

_SYSTEM = """You turn SQL query results into a concise natural-language answer
for a business user. Be brief and factual; do not invent numbers not present
in the rows. If told the results were truncated, mention that explicitly."""


def synthesize_answer(ctx: PipelineContext, llm: LLMClient) -> str:
    execution = ctx.execution
    if execution is None or not execution.success:
        error = execution.error if execution else "unknown error"
        return f"I couldn't produce an answer: {error}"

    rows_preview = execution.rows[:20] if execution.rows else []
    question = ctx.rewritten_question or ctx.raw_question
    user = (
        f"Question: {question}\n"
        f"Columns: {execution.columns}\n"
        f"Rows ({execution.row_count} total{', truncated' if execution.truncated else ''}): {rows_preview}\n"
        "Summarize the answer in 1-3 sentences."
    )
    resp = llm.call_cheap(_SYSTEM, user)
    answer = resp.text.strip()
    if execution.truncated and "truncat" not in answer.lower():
        answer += " (Results were truncated to the first rows.)"
    return answer
