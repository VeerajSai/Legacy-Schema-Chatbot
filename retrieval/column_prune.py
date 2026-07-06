"""Stage 5 (doc section 4): column pruning. Deterministic keyword overlap, no
model — the doc's own reasoning is that this step is cheap and doesn't need
one. PK/FK columns are always kept: a pruned FK guarantees a broken join."""
from __future__ import annotations

import re
from dataclasses import replace

from contracts.types import ColumnCard, GraphExpansionResult, PrunedSchema, TableCard


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _kept_columns(question_tokens: set[str], card: TableCard) -> list[ColumnCard]:
    desc_tokens = _tokens(card.description) | _tokens(" ".join(card.synonyms))
    table_on_topic = bool(question_tokens & desc_tokens)

    kept: list[ColumnCard] = []
    dropped_non_key: list[ColumnCard] = []
    any_column_name_hit = False
    for c in card.columns:
        if c.is_pk or c.fk:  # never prune a join key
            kept.append(c)
            continue
        if question_tokens & _tokens(c.name):
            kept.append(c)
            any_column_name_hit = True
        else:
            dropped_non_key.append(c)

    if not any_column_name_hit and table_on_topic:
        # ponytail: fallback for cryptic all-abbreviated column names (e.g.
        # "amt", "qty") that share no tokens with the question even though the
        # table is clearly on-topic. Ceiling: this table keeps all its
        # columns in that case; revisit with a synonym/description-per-column
        # signal if that proves too generous in practice.
        kept.extend(dropped_non_key)
        dropped_non_key = []

    # preserve original column order
    kept_names = {c.name for c in kept}
    return [c for c in card.columns if c.name in kept_names]


def prune_columns(
    question: str,
    expansion: GraphExpansionResult,
    table_cards_by_name: dict[str, TableCard],
) -> PrunedSchema:
    question_tokens = _tokens(question)

    tables: dict[str, list[str]] = {}
    prompt_lines: list[str] = []
    for name in expansion.all_tables:
        card = table_cards_by_name[name]
        kept_columns = _kept_columns(question_tokens, card)
        tables[name] = [c.name for c in kept_columns]
        pruned_card = replace(card, columns=kept_columns)
        prompt_lines.append(pruned_card.to_prompt_text())

    if expansion.join_paths:
        join_str = "; ".join(
            f"{e.left_table}.{e.left_col} = {e.right_table}.{e.right_col}" for e in expansion.join_paths
        )
        prompt_lines.append(f"-- join path: {join_str}")

    return PrunedSchema(tables=tables, schema_text="\n".join(prompt_lines))
