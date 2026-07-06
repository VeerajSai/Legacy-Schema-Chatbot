"""Shared data contracts threaded between every offline/online pipeline stage.

Frozen first (before parallel build waves) so independent modules can be built
against these shapes without integration conflicts. Any change here needs to be
re-propagated to every consumer.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class ColumnCard:
    name: str
    dtype: str                       # sqlite storage class: INTEGER/TEXT/REAL
    is_pk: bool = False
    fk: str | None = None            # "orders.id" style ref, or None
    fk_declared: bool = False        # True = real SQLite FK constraint, False = inferred
    distinct_values: list[str] | None = None   # populated when < 50 distinct
    nullable: bool = True


@dataclass
class TableCard:
    table: str
    module: str
    description: str                 # LLM-generated, one-time
    row_count: int
    columns: list[ColumnCard]
    synonyms: list[str] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        """Compact schema line for stage-6 prompt assembly, doc section 4 stage 6 format."""
        cols = []
        for c in self.columns:
            bits = [c.name]
            if c.is_pk:
                bits.append("PK")
            if c.fk:
                bits.append(f"FK→{c.fk}")
            if c.distinct_values:
                bits.append("{" + ",".join(c.distinct_values) + "}")
            cols.append(" ".join(bits) if len(bits) == 1 else f"{c.name} ({' '.join(bits[1:])})")
        return f"{self.table}({', '.join(cols)})"

    def to_index_text(self) -> str:
        """Text fed to BM25 + dense embedding indices."""
        col_names = ", ".join(c.name for c in self.columns)
        syns = ", ".join(self.synonyms)
        return f"{self.table} | {self.module} | {self.description} | columns: {col_names} | synonyms: {syns}"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "TableCard":
        cols = [ColumnCard(**c) for c in d["columns"]]
        return TableCard(
            table=d["table"], module=d["module"], description=d["description"],
            row_count=d["row_count"], columns=cols, synonyms=d.get("synonyms", []),
        )


@dataclass
class JoinEdge:
    left_table: str
    left_col: str
    right_table: str
    right_col: str
    declared: bool
    label: str = ""                  # semantic hint, e.g. "manages" vs "works_in"
    confidence: float = 1.0          # 1.0 declared, else profiling score


@dataclass
class RetrievalResult:
    candidate_tables: list[str]      # top 5-8 post-rerank
    scores: dict[str, float] = field(default_factory=dict)
    bm25_top: list[str] = field(default_factory=list)
    dense_top: list[str] = field(default_factory=list)


@dataclass
class GraphExpansionResult:
    all_tables: list[str]            # retrieved + bridge tables
    bridge_tables: list[str] = field(default_factory=list)
    join_paths: list[JoinEdge] = field(default_factory=list)
    ambiguous_paths: list[list[JoinEdge]] = field(default_factory=list)


@dataclass
class PrunedSchema:
    tables: dict[str, list[str]]     # table -> kept column names (PK/FK always kept)
    schema_text: str                 # rendered, prompt-ready


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    parsed_tables: set[str] = field(default_factory=set)
    explain_ok: bool = True
    repaired_sql: str | None = None  # e.g. LIMIT auto-injected


@dataclass
class ExecutionResult:
    success: bool
    rows: list[tuple] | None = None
    columns: list[str] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    error: str | None = None
    elapsed_ms: float = 0.0


@dataclass
class PipelineContext:
    request_id: str
    user_id: str
    role: str
    raw_question: str
    conversation_history: list[dict] = field(default_factory=list)  # [{"question","sql","tables"}]
    rewritten_question: str | None = None
    clarification_question: str | None = None
    blocked_reason: str | None = None        # stage 0 guardrail rejection
    retrieval: RetrievalResult | None = None
    graph: GraphExpansionResult | None = None
    pruned_schema: PrunedSchema | None = None
    sql_candidate: str | None = None
    validation: ValidationResult | None = None
    execution: ExecutionResult | None = None
    answer: str | None = None
    retries: int = 0
    cache_hit: str | None = None     # "exact" | "semantic" | "template" | None
    tokens_used: dict[str, int] = field(default_factory=dict)
    stage_timings_ms: dict[str, float] = field(default_factory=dict)


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
