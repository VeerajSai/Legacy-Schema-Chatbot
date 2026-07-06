"""The single integration point: wires stages 0-11 in order (doc section 4).

Known gap: the per-stage function signatures are fixed by contract (e.g.
`generate_sql(system, user, llm) -> str`) and don't return `LLMResponse`
token counts back up to the orchestrator, so `ctx.tokens_used` is left at
its default `{}` rather than precisely accounted here. Wiring that through
would mean widening those signatures beyond what was specified.
"""
from __future__ import annotations

import json
import time
import uuid

from config.settings import FEWSHOT_BANK_PATH, GLOSSARY_PATH, RETRIEVAL_FINAL_TOP_K
from contracts.llm_client import LLMClient, get_llm_client
from contracts.types import PipelineContext

from pipeline.cache import cache_lookup, cache_store
from pipeline.execution import execute_sql, repair_loop
from pipeline.guardrails import check_guardrails
from pipeline.logger import log_event
from pipeline.prompt_assembly import assemble_prompt
from pipeline.synthesis import synthesize_answer
from pipeline.understanding import understand_question


def _load_json_default(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default
    return default


def _timed(ctx: PipelineContext, name: str, fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    ctx.stage_timings_ms[name] = (time.perf_counter() - start) * 1000
    return result


def answer_question(
    question: str,
    user_id: str,
    role: str,
    conversation: list[dict] | None = None,
    llm: LLMClient | None = None,
) -> PipelineContext:
    llm = llm or get_llm_client()
    ctx = PipelineContext(
        request_id=str(uuid.uuid4()),
        user_id=user_id,
        role=role,
        raw_question=question,
        conversation_history=conversation or [],
    )

    # Stage 0: guardrails.
    blocked_reason = _timed(ctx, "guardrails", check_guardrails, question)
    if blocked_reason:
        ctx.blocked_reason = blocked_reason
        log_event(ctx)
        return ctx

    # Stage 1: cache lookup.
    tier, cached_sql = _timed(ctx, "cache_lookup", cache_lookup, question, role)
    if cached_sql:
        ctx.cache_hit = tier
        ctx.sql_candidate = cached_sql
        ctx.execution = _timed(ctx, "execution", execute_sql, cached_sql)
        ctx.answer = _timed(ctx, "synthesis", synthesize_answer, ctx, llm)
        log_event(ctx)
        return ctx

    # Stage 2: query understanding + ambiguity gate.
    _timed(ctx, "understanding", understand_question, ctx, llm)
    if ctx.clarification_question:
        log_event(ctx)
        return ctx

    # Stages 3-5: retrieval / graph expansion / column pruning. Imported here
    # (module-attribute access, not `from x import y`) rather than at module
    # scope: these packages are owned by parallel agents and may not exist
    # yet, and dotted access is what lets tests `unittest.mock.patch(
    # "retrieval.hybrid_retrieve.retrieve_tables", ...)` take effect.
    import catalog.build_catalog as catalog_mod
    import retrieval.hybrid_retrieve as hybrid_retrieve_mod
    import retrieval.graph_expand as graph_expand_mod
    import retrieval.column_prune as column_prune_mod

    table_cards = _timed(ctx, "load_table_cards", catalog_mod.load_table_cards)
    join_graph = _timed(ctx, "load_join_graph", catalog_mod.load_join_graph)

    query_text = ctx.rewritten_question or ctx.raw_question
    ctx.retrieval = _timed(
        ctx, "retrieval", hybrid_retrieve_mod.retrieve_tables,
        query_text, table_cards, role, RETRIEVAL_FINAL_TOP_K,
    )
    ctx.graph = _timed(
        ctx, "graph_expand", graph_expand_mod.expand_with_graph,
        ctx.retrieval, join_graph, table_cards,
    )
    ctx.pruned_schema = _timed(
        ctx, "column_prune", column_prune_mod.prune_columns,
        query_text, ctx.graph, table_cards,
    )

    # Stage 6: prompt assembly.
    fewshots = _load_json_default(FEWSHOT_BANK_PATH, [])
    glossary = _load_json_default(GLOSSARY_PATH, {})
    system, user = _timed(ctx, "prompt_assembly", assemble_prompt, ctx, fewshots, glossary)

    # Stages 7-9: generate -> validate -> execute, with repair loop.
    _timed(ctx, "generation_repair", repair_loop, ctx, system, user, llm, table_cards)

    # Stage 10: answer synthesis.
    ctx.answer = _timed(ctx, "synthesis", synthesize_answer, ctx, llm)

    # Cache the verified SQL (not the result) for reuse.
    if ctx.execution and ctx.execution.success and ctx.sql_candidate:
        cache_store(question, role, ctx.sql_candidate)

    # Stage 11: logging.
    log_event(ctx)
    return ctx
