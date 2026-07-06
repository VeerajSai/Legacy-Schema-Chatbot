"""Stage 6: prompt assembly, compact schema format not full DDL (doc section
4 stage 6)."""
from __future__ import annotations

from contracts.types import PipelineContext

_DIALECT_RULES = """Dialect: SQLite.
- SELECT-only. No FOR UPDATE, no DDL/DML.
- Always alias tables and qualify columns with their alias.
- Always include LIMIT unless the query is a pure aggregation (COUNT/SUM/AVG with no GROUP BY, or GROUP BY that already bounds row count).
- Prefer explicit JOIN ... ON using the join paths given below.
- Output SQL only, in a single fenced ```sql code block."""


def assemble_prompt(ctx: PipelineContext, fewshots: list[dict], glossary: dict) -> tuple[str, str]:
    schema_text = ctx.pruned_schema.schema_text if ctx.pruned_schema else ""

    fewshot_text = "\n\n".join(
        f"Q: {ex.get('question', '')}\nSQL: {ex.get('sql', '')}" for ex in fewshots[:3]
    )

    glossary_text = "\n".join(f"- {term}: {definition}" for term, definition in glossary.items())

    system = (
        "You are a SQL generation engine for a legacy business database.\n\n"
        f"{_DIALECT_RULES}\n\n"
        f"Schema:\n{schema_text}\n\n"
        + (f"Glossary:\n{glossary_text}\n\n" if glossary_text else "")
        + (f"Examples:\n{fewshot_text}\n" if fewshot_text else "")
    )

    question = ctx.rewritten_question or ctx.raw_question
    user = f"Question: {question}"
    return system, user
