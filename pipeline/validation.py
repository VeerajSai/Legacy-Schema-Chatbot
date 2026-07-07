"""Stage 8: static validation before touching the DB, cheapest checks first
(doc section 4 stage 8 / section 8 security model)."""
from __future__ import annotations

import sqlglot
from sqlglot import exp

from contracts.db import get_connection
from contracts.rbac import allowed_modules
from contracts.types import TableCard, ValidationResult

_DML_DDL_NODES = (exp.Delete, exp.Drop, exp.Insert, exp.Update, exp.Alter, exp.Create)


def _is_pure_aggregation(tree: exp.Expression) -> bool:
    """No LIMIT needed if the query is already row-bounded by aggregation
    (an aggregate function with no GROUP BY collapses to one row)."""
    if tree.find(exp.Group):
        return False
    return bool(list(tree.find_all(exp.AggFunc)))


def validate_sql(sql: str, table_cards_by_name: dict[str, TableCard], role: str) -> ValidationResult:
    errors: list[str] = []

    try:
        tree = sqlglot.parse_one(sql, dialect="sqlite")
    except Exception as e:  # sqlglot raises its own ParseError subclasses
        return ValidationResult(is_valid=False, errors=[f"parse error: {e}"])

    if tree is None:
        return ValidationResult(is_valid=False, errors=["parse error: empty statement"])

    # Policy lint: SELECT-only.
    if isinstance(tree, _DML_DDL_NODES) or tree.find(*_DML_DDL_NODES):
        return ValidationResult(is_valid=False, errors=["policy violation: only SELECT statements are allowed"])
    if not isinstance(tree, exp.Query):
        return ValidationResult(is_valid=False, errors=["policy violation: only SELECT statements are allowed"])

    cte_names = {c.alias_or_name for c in tree.find_all(exp.CTE)}
    parsed_tables = {t.name for t in tree.find_all(exp.Table)} - cte_names

    # Schema lint: every referenced table/column exists in the catalog.
    for table_name in parsed_tables:
        if table_name not in table_cards_by_name:
            errors.append(f"hallucinated identifier: table '{table_name}' not in schema catalog")

    # Column existence check (best-effort: only checks columns whose table
    # qualifier we can resolve — alias -> table mapping).
    alias_to_table = {}
    for t in tree.find_all(exp.Table):
        alias_to_table[t.alias_or_name] = t.name
    known_columns_by_table = {
        name: {c.name for c in card.columns} for name, card in table_cards_by_name.items()
    }
    for col in tree.find_all(exp.Column):
        table_alias = col.table
        if not table_alias:
            continue
        table_name = alias_to_table.get(table_alias)
        if table_name is None or table_name not in table_cards_by_name:
            continue  # already reported as missing table, or unresolvable alias
        if col.name not in known_columns_by_table.get(table_name, set()):
            errors.append(f"hallucinated identifier: column '{table_alias}.{col.name}' not in table '{table_name}'")

    # RBAC re-enforcement (belt and suspenders — retrieval already filtered).
    allowed = allowed_modules(role)
    for table_name in parsed_tables:
        card = table_cards_by_name.get(table_name)
        if card is not None and card.module not in allowed:
            errors.append(f"RBAC violation: table '{table_name}' (module '{card.module}') not permitted for role '{role}'")

    if errors:
        return ValidationResult(is_valid=False, errors=errors, parsed_tables=parsed_tables)

    # Auto-inject LIMIT if missing and not a pure aggregation.
    repaired_sql = None
    if tree.find(exp.Limit) is None and not _is_pure_aggregation(tree):
        tree = tree.limit(1000)
        repaired_sql = tree.sql(dialect="sqlite")

    # EXPLAIN QUERY PLAN dry run to catch obvious errors before real execution.
    explain_ok = True
    final_sql = repaired_sql or sql
    try:
        conn = get_connection(read_only=True)
        try:
            conn.execute(f"EXPLAIN QUERY PLAN {final_sql}")
        finally:
            conn.close()
    except Exception as e:
        explain_ok = False
        errors.append(f"EXPLAIN dry run failed: {e}")

    return ValidationResult(
        is_valid=explain_ok,
        errors=errors,
        parsed_tables=parsed_tables,
        explain_ok=explain_ok,
        repaired_sql=repaired_sql,
    )
