"""Recovers undeclared FKs by profiling the live DB — legacy schemas rarely
declare every constraint, so retrieval/join-graph quality depends on finding
these ourselves rather than trusting PRAGMA foreign_key_list alone.

Heuristic: for every column that isn't already a declared FK, check if its
name exactly matches or ends with some other table's single-column PK name.
Any such candidate is then verified with an inclusion-dependency check
(distinct non-null values of the column must be a subset of the referenced
PK's value set) against the live data — naming alone is not proof.
"""
from __future__ import annotations

from contracts.db import get_connection
from contracts.types import JoinEdge

INFERRED_CONFIDENCE = 0.8


def _declared_fk_columns(crawled: dict) -> set[tuple[str, str]]:
    return {(t, fk["column"]) for t, info in crawled.items() for fk in info["fks"]}


def _single_col_pk_map(crawled: dict) -> dict[str, str]:
    """{pk_column_name: table} for tables with exactly one PK column."""
    pk_map: dict[str, str] = {}
    for t, info in crawled.items():
        pk_cols = [c["name"] for c in info["columns"] if c["pk"]]
        if len(pk_cols) == 1:
            pk_map[pk_cols[0]] = t
    return pk_map


def _candidate_pairs(crawled: dict, pk_map: dict[str, str]):
    """Yields (table, column, ref_table, ref_column) name-match candidates,
    excluding columns already declared as FKs and a table's own PK."""
    declared = _declared_fk_columns(crawled)
    for t, info in crawled.items():
        for c in info["columns"]:
            name = c["name"]
            if c["pk"] or (t, name) in declared:
                continue
            for pk_name, ref_table in pk_map.items():
                if ref_table == t:
                    continue
                if name == pk_name or name.endswith("_" + pk_name):
                    yield t, name, ref_table, pk_name


def infer_foreign_keys(crawled: dict) -> list[JoinEdge]:
    pk_map = _single_col_pk_map(crawled)
    conn = get_connection(read_only=True)
    edges: list[JoinEdge] = []
    try:
        cur = conn.cursor()
        for table, column, ref_table, ref_column in _candidate_pairs(crawled, pk_map):
            values = {
                row[0] for row in cur.execute(
                    f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL"
                ).fetchall()
            }
            if not values:
                continue  # nothing to check containment against
            ref_values = {
                row[0] for row in cur.execute(
                    f"SELECT DISTINCT {ref_column} FROM {ref_table}"
                ).fetchall()
            }
            if values <= ref_values:
                edges.append(JoinEdge(
                    left_table=table, left_col=column,
                    right_table=ref_table, right_col=ref_column,
                    declared=False, confidence=INFERRED_CONFIDENCE,
                ))
    finally:
        conn.close()
    return edges
