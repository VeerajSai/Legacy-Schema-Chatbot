"""Orchestrates the offline catalog build: crawl -> describe -> enumerations ->
fk_inference -> join_graph -> glossary -> fewshot_bank -> table cards.
Runnable as `python -m catalog.build_catalog`.
"""
from __future__ import annotations

import json
from pathlib import Path

from config.settings import JOIN_GRAPH_PATH, TABLE_CARDS_PATH
from contracts.types import ColumnCard, TableCard
from db.schema_spec import TABLES as SCHEMA_TABLES

from catalog.crawler import crawl
from catalog.describe import describe_tables
from catalog.enumerations import enumerate_low_cardinality
from catalog.fewshot_bank import build_fewshot_bank
from catalog.fk_inference import infer_foreign_keys
from catalog.glossary import build_glossary
from catalog.join_graph import build_join_graph, load_join_graph, save_join_graph

__all__ = ["build_catalog", "load_table_cards", "load_join_graph"]


def _modules(crawled: dict) -> dict[str, str]:
    # module is metadata about the schema design, not something you can
    # introspect from the live DB -- legitimate to read off schema_spec here
    # (task brief: "fine to know which tables/modules exist").
    return {t: SCHEMA_TABLES[t]["module"] for t in crawled if t in SCHEMA_TABLES}


def _build_table_cards(crawled, descriptions, enums, inferred_edges, synonyms, modules) -> dict[str, TableCard]:
    inferred_fk: dict[str, dict[str, str]] = {}
    for e in inferred_edges:
        inferred_fk.setdefault(e.left_table, {})[e.left_col] = f"{e.right_table}.{e.right_col}"

    cards: dict[str, TableCard] = {}
    for t, info in crawled.items():
        declared_fk = {fk["column"]: f'{fk["ref_table"]}.{fk["ref_column"]}' for fk in info["fks"]}
        columns = []
        for c in info["columns"]:
            name = c["name"]
            fk_target = declared_fk.get(name) or inferred_fk.get(t, {}).get(name)
            columns.append(ColumnCard(
                name=name, dtype=c["dtype"], is_pk=c["pk"],
                fk=fk_target, fk_declared=name in declared_fk,
                distinct_values=enums.get(t, {}).get(name),
                nullable=not c["notnull"],
            ))
        cards[t] = TableCard(
            table=t, module=modules.get(t, "unknown"),
            description=descriptions.get(t, ""), row_count=info["row_count"],
            columns=columns, synonyms=synonyms.get(t, []),
        )
    return cards


def build_catalog() -> dict[str, TableCard]:
    crawled = crawl()
    modules = _modules(crawled)

    descriptions = describe_tables(crawled, modules)
    enums = enumerate_low_cardinality(crawled)
    inferred_edges = infer_foreign_keys(crawled)
    synonyms = build_glossary()
    build_fewshot_bank()

    cards = _build_table_cards(crawled, descriptions, enums, inferred_edges, synonyms, modules)

    G = build_join_graph(crawled, inferred_edges, modules)
    save_join_graph(G)

    TABLE_CARDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TABLE_CARDS_PATH.write_text(json.dumps([c.to_dict() for c in cards.values()], indent=2))
    return cards


def load_table_cards(path=TABLE_CARDS_PATH) -> dict[str, TableCard]:
    data = json.loads(Path(path).read_text())
    return {d["table"]: TableCard.from_dict(d) for d in data}


if __name__ == "__main__":
    built = build_catalog()
    print(f"Built {len(built)} table cards -> {TABLE_CARDS_PATH}")
    print(f"Join graph -> {JOIN_GRAPH_PATH}")
