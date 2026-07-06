"""Stage 3 (doc section 4): BM25 keyword index over table cards — catches exact
jargon and table-name matches that dense retrieval alone misses."""
from __future__ import annotations

from rank_bm25 import BM25Okapi

from contracts.types import TableCard


class BM25Index:
    def __init__(self) -> None:
        self._table_names: list[str] = []
        self._bm25: BM25Okapi | None = None

    def build(self, table_cards: dict[str, TableCard]) -> None:
        self._table_names = list(table_cards.keys())
        corpus = [table_cards[name].to_index_text().lower().split() for name in self._table_names]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def scores(self, question: str) -> dict[str, float]:
        if self._bm25 is None:
            return {}
        raw = self._bm25.get_scores(question.lower().split())
        return dict(zip(self._table_names, raw))

    def query(self, question: str, top_n: int) -> list[str]:
        ranked = sorted(self.scores(question).items(), key=lambda p: p[1], reverse=True)
        return [name for name, _ in ranked[:top_n]]
