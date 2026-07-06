"""Stage 2: query understanding, cheap model (doc section 4 stage 2)."""
from __future__ import annotations

import json
import re

from contracts.llm_client import LLMClient
from contracts.types import PipelineContext

_SYSTEM = """You rewrite a user's question about a company database into a
self-contained question, using the conversation history to resolve
references like "that" or "last month". You also detect genuine ambiguity
(e.g. "revenue" could mean gross or net; "customers" could mean accounts or
contacts) — if and only if the question is truly ambiguous, ask exactly ONE
clarifying question with concrete options instead of guessing.

Respond with ONLY a JSON object, no other text:
{"rewritten": "<self-contained question>", "ambiguous": <true|false>, "clarifying_question": "<question or empty string>"}
"""


def _history_text(history: list[dict]) -> str:
    lines = []
    for turn in history:
        q = turn.get("question", "")
        sql = turn.get("sql", "")
        lines.append(f"Q: {q}" + (f" | SQL: {sql}" if sql else ""))
    return "\n".join(lines)


def _extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


def understand_question(ctx: PipelineContext, llm: LLMClient) -> None:
    user = f"Conversation so far:\n{_history_text(ctx.conversation_history)}\n\nNew question: {ctx.raw_question}"
    resp = llm.call_cheap(_SYSTEM, user)
    parsed = _extract_json(resp.text)
    if not parsed:
        ctx.rewritten_question = ctx.raw_question
        return
    ctx.rewritten_question = parsed.get("rewritten") or ctx.raw_question
    if parsed.get("ambiguous") and parsed.get("clarifying_question"):
        ctx.clarification_question = parsed["clarifying_question"]
