"""Stage 3 (doc section 4): dense retrieval over table cards. Brute-force numpy
cosine similarity — 74 tables doesn't warrant FAISS."""
from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from config.settings import DENSE_MODEL_NAME
from contracts.types import TableCard

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    # ponytail: module-level singleton, model load is slow (~seconds) and this
    # process may build many indices (one per retrieve_tables call in tests).
    global _model
    if _model is None:
        _model = SentenceTransformer(DENSE_MODEL_NAME)
    return _model


class EmbedIndex:
    def __init__(self) -> None:
        self._table_names: list[str] = []
        self._embeddings: np.ndarray | None = None

    def build(self, table_cards: dict[str, TableCard]) -> None:
        self._table_names = list(table_cards.keys())
        if not self._table_names:
            self._embeddings = None
            return
        texts = [table_cards[name].to_index_text() for name in self._table_names]
        self._embeddings = _get_model().encode(texts, normalize_embeddings=True)

    def scores(self, question: str) -> dict[str, float]:
        if self._embeddings is None:
            return {}
        q_emb = _get_model().encode([question], normalize_embeddings=True)[0]
        sims = self._embeddings @ q_emb
        return dict(zip(self._table_names, sims.tolist()))

    def query(self, question: str, top_n: int) -> list[str]:
        ranked = sorted(self.scores(question).items(), key=lambda p: p[1], reverse=True)
        return [name for name, _ in ranked[:top_n]]
