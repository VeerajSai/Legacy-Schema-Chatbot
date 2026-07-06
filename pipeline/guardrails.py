"""Stage 0: input guardrails. Regex/keyword only — no model call, ~0 tokens
(doc section 4 stage 0)."""
from __future__ import annotations

import re

# Imperative DML/DDL verbs targeting data, not just the word appearing in prose
# (e.g. "show me updates" shouldn't trip "update").
_DML_PATTERNS = [
    re.compile(r"\bdelete\s+(from|all|every)\b", re.I),
    re.compile(r"\bdrop\s+(table|database|schema|index|view)\b", re.I),
    re.compile(r"\bupdate\s+\w+\s+set\b", re.I),
    re.compile(r"\binsert\s+into\b", re.I),
    re.compile(r"\btruncate\s+(table)?\b", re.I),
    re.compile(r"\balter\s+table\b", re.I),
]

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(the\s+)?(previous|above|prior)\s+instructions", re.I),
    re.compile(r"\byou\s+are\s+now\b", re.I),
    re.compile(r"\bsystem\s+prompt\b", re.I),
    re.compile(r"reveal\s+your\s+(instructions|prompt)", re.I),
]


def check_guardrails(question: str) -> str | None:
    """Returns a rejection reason string if the question should be blocked,
    else None."""
    for pattern in _DML_PATTERNS:
        if pattern.search(question):
            return "blocked: question expresses data-modifying (DML/DDL) intent"
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(question):
            return "blocked: possible prompt-injection attempt"
    return None
