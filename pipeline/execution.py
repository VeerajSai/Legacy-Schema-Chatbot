"""Stage 9: execution + repair loop (doc section 4 stage 9).

Known limitation: sqlite has no native statement timeout, so the doc's 30s
statement-timeout requirement is skipped rather than built as a thread-based
watchdog — not worth it for this dataset size.
"""
from __future__ import annotations

import re
import time

import sqlglot
from sqlglot import exp

from config.settings import EXECUTION_ROW_CAP, MAX_REPAIR_RETRIES
from contracts.db import get_connection
from contracts.llm_client import LLMClient
from contracts.types import ExecutionResult, PipelineContext, TableCard
from pipeline.generation import generate_sql
from pipeline.validation import validate_sql


def execute_sql(sql: str) -> ExecutionResult:
    start = time.perf_counter()
    try:
        conn = get_connection(read_only=True)
        try:
            cur = conn.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            fetched = cur.fetchmany(EXECUTION_ROW_CAP + 1)
        finally:
            conn.close()
    except Exception as e:
        return ExecutionResult(
            success=False, error=str(e), elapsed_ms=(time.perf_counter() - start) * 1000
        )

    truncated = len(fetched) > EXECUTION_ROW_CAP
    rows = [tuple(r) for r in fetched[:EXECUTION_ROW_CAP]]
    return ExecutionResult(
        success=True,
        rows=rows,
        columns=columns,
        row_count=len(rows),
        truncated=truncated,
        elapsed_ms=(time.perf_counter() - start) * 1000,
    )


def _string_literal_fixups(sql: str, table_cards_by_name: dict[str, TableCard]) -> str | None:
    """Empty-result sanity check: find string-literal filters whose case
    doesn't match the catalog's enumerated distinct_values, and return a
    corrected SQL string (case-fixed), or None if nothing to fix."""
    try:
        tree = sqlglot.parse_one(sql, dialect="sqlite")
    except Exception:
        return None

    alias_to_table = {t.alias_or_name: t.name for t in tree.find_all(exp.Table)}
    sole_table = next(iter(alias_to_table.values())) if len(alias_to_table) == 1 else None

    fixed_sql = sql
    changed = False
    for node in tree.find_all(exp.EQ, exp.In, exp.NEQ):
        col_node = node.find(exp.Column)
        lit_node = node.find(exp.Literal)
        if col_node is None or lit_node is None or not lit_node.is_string:
            continue
        table_name = alias_to_table.get(col_node.table) or sole_table
        card = table_cards_by_name.get(table_name) if table_name else None
        if card is None:
            continue
        col_card = next((c for c in card.columns if c.name == col_node.name), None)
        if not col_card or not col_card.distinct_values:
            continue
        literal_value = lit_node.this
        for candidate in col_card.distinct_values:
            if candidate.lower() == literal_value.lower() and candidate != literal_value:
                pattern = re.compile(r"(['\"])" + re.escape(literal_value) + r"\1")
                new_sql = pattern.sub(f"'{candidate}'", fixed_sql, count=1)
                if new_sql != fixed_sql:
                    fixed_sql = new_sql
                    changed = True
                break
    return fixed_sql if changed else None


_REPAIR_SYSTEM_SUFFIX = """

The previous SQL failed. Fix ONLY the specific error below and return the
corrected query in a fenced ```sql code block.
Failing SQL:
{sql}

Error:
{error}
"""


def repair_loop(
    ctx: PipelineContext,
    system: str,
    user: str,
    llm: LLMClient,
    table_cards_by_name: dict[str, TableCard],
    max_retries: int = MAX_REPAIR_RETRIES,
) -> None:
    attempt_system, attempt_user = system, user
    for attempt in range(max_retries + 1):
        sql = generate_sql(attempt_system, attempt_user, llm)
        validation = validate_sql(sql, table_cards_by_name, ctx.role)
        final_sql = validation.repaired_sql or sql

        if not validation.is_valid:
            ctx.sql_candidate = sql
            ctx.validation = validation
            ctx.execution = ExecutionResult(success=False, error="; ".join(validation.errors))
            ctx.retries = attempt
            if attempt < max_retries:
                attempt_system = system + _REPAIR_SYSTEM_SUFFIX.format(sql=sql, error=ctx.execution.error)
                attempt_user = user
                continue
            return

        execution = execute_sql(final_sql)
        ctx.sql_candidate = final_sql
        ctx.validation = validation
        ctx.execution = execution
        ctx.retries = attempt

        if execution.success:
            if execution.row_count == 0:
                fixed_sql = _string_literal_fixups(final_sql, table_cards_by_name)
                if fixed_sql:
                    retry_execution = execute_sql(fixed_sql)
                    if retry_execution.success and retry_execution.row_count > 0:
                        ctx.sql_candidate = fixed_sql
                        ctx.execution = retry_execution
            return

        if attempt < max_retries:
            attempt_system = system + _REPAIR_SYSTEM_SUFFIX.format(sql=final_sql, error=execution.error)
            attempt_user = user
            continue
        return
