"""Stage 1: three-tier cache (exact / semantic / template), doc section 4
stage 1. RBAC-scoped keys — role is part of every lookup/store so a cached
admin query never leaks to a restricted role."""
from __future__ import annotations

import hashlib
import re
import sqlite3
import time

import numpy as np

from config.settings import CACHE_DB_PATH, SEMANTIC_CACHE_THRESHOLD, EXACT_CACHE_TTL_SECONDS

# ponytail: only relative date phrases collapse to <DATE> — two different
# absolute periods (march vs january, 2024 vs 2026) must hash to different
# template keys since the cached SQL has the literal period baked in with no
# re-parameterization. A relative phrase re-hitting within TTL is fine
# because a real system would generate SQL with relative date functions.
_TEMPLATE_PATTERNS = [
    re.compile(r"\blast\s+(quarter|month|year|week)\b", re.I),
    re.compile(r"\bthis\s+(quarter|month|year|week)\b", re.I),
]

_SEMANTIC_CACHE_CAP = 500

# ponytail: flat "operational" TTL bucket by default; only switch to the
# longer "historical" bucket when the question smells like an aggregate over
# a fixed past period. Good enough for a demo-scale cache; a real system
# would classify volatility per-table instead of per-question-keyword.
_HISTORICAL_HINTS = re.compile(r"\b(last year|total|ytd|year.to.date|historical|all time)\b", re.I)


def _normalize(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def _templatize(question: str) -> str:
    text = _normalize(question)
    for pattern in _TEMPLATE_PATTERNS:
        text = pattern.sub("<DATE>", text)
    return text


def _hash(text: str, role: str) -> str:
    return hashlib.sha256(f"{role}::{text}".encode("utf-8")).hexdigest()


def _ttl_seconds(question: str) -> int:
    if _HISTORICAL_HINTS.search(question):
        return EXACT_CACHE_TTL_SECONDS["historical"]
    return EXACT_CACHE_TTL_SECONDS["operational"]


_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        from config.settings import DENSE_MODEL_NAME
        _embedder = SentenceTransformer(DENSE_MODEL_NAME)
    return _embedder


def _connect() -> sqlite3.Connection:
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS exact_cache (
            key TEXT PRIMARY KEY, role TEXT, question TEXT, sql TEXT, created_at REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS template_cache (
            key TEXT PRIMARY KEY, role TEXT, question TEXT, sql TEXT, created_at REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS semantic_cache (
            role TEXT, question TEXT, sql TEXT, embedding BLOB, created_at REAL
        )"""
    )
    return conn


def cache_lookup(question: str, role: str) -> tuple[str | None, str | None]:
    """Returns (tier, cached_sql) or (None, None). Checks exact, then
    template, then semantic — cheapest first."""
    conn = _connect()
    try:
        norm = _normalize(question)
        exact_key = _hash(norm, role)
        row = conn.execute(
            "SELECT sql, created_at FROM exact_cache WHERE key = ?", (exact_key,)
        ).fetchone()
        if row is not None:
            sql, created_at = row
            if time.time() - created_at <= _ttl_seconds(question):
                return "exact", sql

        template_key = _hash(_templatize(question), role)
        row = conn.execute(
            "SELECT sql, created_at FROM template_cache WHERE key = ?", (template_key,)
        ).fetchone()
        if row is not None:
            sql, created_at = row
            if time.time() - created_at <= _ttl_seconds(question):
                return "template", sql

        rows = conn.execute(
            "SELECT sql, embedding FROM semantic_cache WHERE role = ?", (role,)
        ).fetchall()
        if rows:
            query_vec = _get_embedder().encode([norm])[0].astype("float32")
            query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-9)
            matrix = np.array([np.frombuffer(blob, dtype="float32") for _sql, blob in rows])
            scores = matrix @ query_vec
            best_idx = int(np.argmax(scores))
            if float(scores[best_idx]) >= SEMANTIC_CACHE_THRESHOLD:
                return "semantic", rows[best_idx][0]
        return None, None
    finally:
        conn.close()


def cache_store(question: str, role: str, sql: str) -> None:
    conn = _connect()
    try:
        now = time.time()
        norm = _normalize(question)
        conn.execute(
            "INSERT OR REPLACE INTO exact_cache (key, role, question, sql, created_at) VALUES (?,?,?,?,?)",
            (_hash(norm, role), role, question, sql, now),
        )
        conn.execute(
            "INSERT OR REPLACE INTO template_cache (key, role, question, sql, created_at) VALUES (?,?,?,?,?)",
            (_hash(_templatize(question), role), role, question, sql, now),
        )
        vec = _get_embedder().encode([norm])[0].astype("float32")
        vec = vec / (np.linalg.norm(vec) + 1e-9)

        # ponytail: prune-on-insert row cap, not a background eviction job —
        # revisit if semantic_cache write volume ever makes this the hot path.
        count = conn.execute(
            "SELECT COUNT(*) FROM semantic_cache WHERE role = ?", (role,)
        ).fetchone()[0]
        if count >= _SEMANTIC_CACHE_CAP:
            old_rowids = conn.execute(
                "SELECT rowid FROM semantic_cache WHERE role = ? ORDER BY created_at ASC LIMIT ?",
                (role, count - _SEMANTIC_CACHE_CAP + 1),
            ).fetchall()
            conn.executemany(
                "DELETE FROM semantic_cache WHERE rowid = ?", old_rowids
            )

        conn.execute(
            "INSERT INTO semantic_cache (role, question, sql, embedding, created_at) VALUES (?,?,?,?,?)",
            (role, question, sql, vec.tobytes(), now),
        )
        conn.commit()
    finally:
        conn.close()
