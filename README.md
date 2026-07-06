# NL2SQL Chatbot over a 74-Table Legacy Schema

A chatbot that turns natural-language questions into SQL, retrieving only the
schema slice a question needs instead of stuffing an entire legacy database
into every prompt. This repo implements the design in
[`docs/original-design-doc.md`](docs/original-design-doc.md) — read that
first for the "why."

## Scope disclosure

This is a portfolio-scale build of a production design, substituting for cost
and time reasons, not because the substitutions are architecturally
different:

| Doc calls for | This repo uses | Why it's a reasonable substitution |
|---|---|---|
| Postgres/Oracle/MySQL, 100+ tables | SQLite, 74 tables (`db/schema_spec.py`) | The design is explicitly "scale-insensitive up to a few thousand tables" (doc §5) — per-query cost depends on retrieved slice size, not total table count. SQLite lets the whole thing run with zero infra |
| Hosted vector DB for metadata embeddings | Local `sentence-transformers` + `rank_bm25` | Doc §3.2 says an in-memory graph/index is "simpler and faster" until you're at thousands of tables across many DBs; a hosted vector DB is an ops dependency this scale doesn't need |
| Multi-provider LLM routing | Single provider (Anthropic), cheap/strong model routing (doc's stage-routing rule) | The cost lever the doc actually argues for is cheap-vs-strong routing, not multi-provider redundancy; `contracts/llm_client.py` isolates the provider behind an ABC so adding a second one later is a small diff |
| Grafana/Prometheus dashboards | JSONL event log + `eval/metrics.py` CLI | Same metrics doc §7 asks for (cache hit rate by tier, tokens/query, latency p50/p95, error rate) — just printed instead of graphed |
| Docker/Kubernetes | Plain `uvicorn`/`streamlit` processes | Nothing in the pipeline assumes in-process execution; containerizing later is additive, not a rewrite |

## Quickstart (Windows / PowerShell)

```powershell
pip install -r requirements.txt
$env:ANTHROPIC_API_KEY = "sk-..."     # optional; falls back to a deterministic stub without it
python -m db.build --seed 42
python -m catalog.build_catalog
python -m eval.build_golden_set
pytest
streamlit run ui/app.py             # or: uvicorn api.server:app --reload
python -m eval.run_eval
```

Or run the whole offline pipeline in one shot: `python scripts/build_all.py`.

## Architecture

Two planes: an **offline plane** that crawls the schema once (and on drift)
into table cards + a join graph + a glossary + a few-shot bank, and an
**online plane** that answers each question through 12 stages — guardrails,
cache, understanding, hybrid retrieval, graph expansion, column pruning,
prompt assembly, generation, validation, execution/repair, synthesis,
logging — all threaded through one `PipelineContext`
(`contracts/types.py`). See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the
full diagrams and the stage-by-stage file map.

## Repo layout

```
api/            FastAPI app (POST /chat, GET /health)
catalog/        Offline plane: crawler, describe, enumerations, fk_inference,
                join_graph, glossary, fewshot_bank -> catalog/artifacts/*.json
config/         Settings, paths, thresholds, RBAC config
contracts/      Frozen shared types/DB helper/LLM client/RBAC -- the seam
                every other module builds against
db/             Legacy schema spec + synthetic data generator -> data/legacy.db
docs/           The original design doc this repo implements
eval/           Golden set (hand-written + DB-resolved), metrics, eval runner
pipeline/       Online plane: guardrails -> cache -> understanding ->
                prompt_assembly -> generation -> validation -> execution ->
                synthesis -> logger, orchestrated by orchestrator.py
retrieval/      BM25 + dense hybrid retrieval, graph expansion, column pruning
scripts/        build_all.py -- regenerate DB + catalog + golden set from scratch
tests/          pytest suite
ui/             Streamlit chat app
```

## Eval results

The full pipeline is wired and runs end-to-end against all 56 golden
questions with **zero crashes or exceptions**. Without a real
`ANTHROPIC_API_KEY` the SQL-generation stage falls back to a deterministic
stub (`SELECT 1`), so execution accuracy is 0% by construction — that's
expected, not a bug, and this run's real purpose is to prove the plumbing
(retrieval → graph expansion → RBAC filtering → validation → execution →
caching) holds together end to end:

```
=== Execution accuracy (stub LLM, no API key) ===
Overall: 0/56 (0.0%)
  agg_window                   0/10 (0.0%)
  join_2_3                     0/20 (0.0%)
  multi_hop_cross_module       0/14 (0.0%)
  single_table                 0/12 (0.0%)

Errors/exceptions: 0/56
```

Confirmed working in this same integration pass (see `ARCHITECTURE.md` for
the stages involved):
- **RBAC filtering** — an `hr_admin`-scoped question about revenue/regions
  retrieves only `hr`/`core` module tables (`department`, `employee`,
  `emp_dept_assign`, `position_mst`, ...), never `finance`/`sales` tables,
  even though nothing in the question says "HR"
- **Guardrails** — "Delete all orders from the database" is blocked before
  it reaches generation
- **Caching** — a repeated question is served from the exact-cache tier
  (persists across process restarts via `data/cache.db`)
- **Disjoint-path handling** — the department↔employee "manages" vs
  "works_in" trap surfaces as two distinct labeled edges rather than
  collapsing to one (see `tests/test_join_graph.py`,
  `tests/test_graph_expand.py`)

Set `ANTHROPIC_API_KEY` and re-run `python -m eval.run_eval` for real
execution-accuracy numbers — the harness and golden set are ready, the
only missing ingredient is a live model.

## Known limitations

- No online feedback loop: no thumbs up/down, no "report wrong answer"
  triage queue, no corrected-pairs flywheel back into the golden set or
  few-shot bank (doc §6's "non-negotiable for production" loop is out of
  scope here)
- No shadow mode against real user traffic (there is no real user traffic —
  the DB is synthetic)
- No fine-tuning path; doc §10 only makes this worthwhile past ~5K verified
  (question, SQL) pairs
- Single-tenant; RBAC is config-driven module filtering
  (`config/rbac.yaml`), not real per-tenant DB grants
- SQLite has no real statement timeout or query cost estimator, so the
  `EXECUTION_TIMEOUT_SECONDS` setting is aspirational here — a real Postgres
  deployment would enforce it at the connection/pool level
- The golden set is ~56 hand-written pairs, not the 200-500 mined-from-logs
  set doc §6 calls for (there are no real query logs for a synthetic DB)
- `PipelineContext.tokens_used` isn't populated yet (the per-stage functions
  don't plumb `LLMResponse.input_tokens`/`output_tokens` back to the
  orchestrator) — `eval/metrics.py`'s tokens/query reporting is ready but
  has nothing to summarize until that's wired up
- A cache hit skips retrieval, so `tables_used` is empty on cached answers
  (the cache remembers the SQL, not which tables it touched)

## License

MIT — see [LICENSE](LICENSE).
