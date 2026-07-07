"""Stage 3 (doc section 4): hybrid retrieval — RBAC filter, then BM25 + dense
union, then cross-encoder rerank down to the final candidate set."""
from __future__ import annotations

from sentence_transformers import CrossEncoder

from config.settings import CROSS_ENCODER_NAME, RETRIEVAL_FINAL_TOP_K, RETRIEVAL_UNION_TOP_N
from contracts.rbac import filter_tables_by_role
from contracts.types import RetrievalResult, TableCard
from retrieval.bm25_index import BM25Index
from retrieval.embed_index import EmbedIndex

_cross_encoder: CrossEncoder | None = None
# ponytail: process-lifetime cache of built indices, keyed by (role, table
# set) -- the RBAC-scoped table set for a role is static within a running
# process (same assumption contracts/rbac.py's lru_cache already makes about
# static config), but keying on role alone would serve a stale index if the
# same role is ever scoped against a different table set in the same
# process (e.g. tests reusing a role across fixtures). Keying on the actual
# table names is cheap and makes that impossible instead of just unlikely.
_indices_by_role: dict[tuple[str, tuple[str, ...]], tuple[BM25Index, EmbedIndex]] = {}


def _get_cross_encoder() -> CrossEncoder:
    global _cross_encoder  # ponytail: singleton, same reasoning as embed_index's model cache
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder(CROSS_ENCODER_NAME)
    return _cross_encoder


def _get_indices(role: str, scoped_cards: dict[str, TableCard]) -> tuple[BM25Index, EmbedIndex]:
    cache_key = (role, tuple(sorted(scoped_cards)))
    if cache_key not in _indices_by_role:
        bm25 = BM25Index()
        bm25.build(scoped_cards)
        dense = EmbedIndex()
        dense.build(scoped_cards)
        _indices_by_role[cache_key] = (bm25, dense)
    return _indices_by_role[cache_key]


def retrieve_tables(
    question: str,
    table_cards: dict[str, TableCard],
    role: str,
    top_k: int = RETRIEVAL_FINAL_TOP_K,
) -> RetrievalResult:
    # RBAC first: a restricted role must never see candidates outside its modules.
    allowed = filter_tables_by_role({name: c.module for name, c in table_cards.items()}, role)
    scoped_cards = {name: c for name, c in table_cards.items() if name in allowed}

    bm25, dense = _get_indices(role, scoped_cards)

    bm25_top = bm25.query(question, RETRIEVAL_UNION_TOP_N)
    dense_top = dense.query(question, RETRIEVAL_UNION_TOP_N)
    union = list(dict.fromkeys(bm25_top + dense_top))  # de-dup, keep first-seen order

    if not union:
        return RetrievalResult(candidate_tables=[], bm25_top=bm25_top, dense_top=dense_top)

    pairs = [(question, scoped_cards[name].to_index_text()) for name in union]
    rerank_scores = _get_cross_encoder().predict(pairs)

    ranked = sorted(zip(union, rerank_scores), key=lambda p: p[1], reverse=True)[:top_k]
    return RetrievalResult(
        candidate_tables=[name for name, _ in ranked],
        scores={name: float(score) for name, score in ranked},
        bm25_top=bm25_top,
        dense_top=dense_top,
    )
