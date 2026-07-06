"""Stage 1: three-tier cache (exact / semantic / template), doc section 4
stage 1. RBAC-scoped keys — role is part of every lookup/store so a cached
admin query never leaks to a restricted role."""
from __future__ import annotations

import hashlib
import re
import sqlite3
import time

from config.settings import CACHE_DB_PATH, SEMANTIC_CACHE_THRESHOLD, EXACT_CACHE_TTL_SECONDS

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|"
    "november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)
_TEMPLATE_PATTERNS = [
    re.compile(r"\b(" + _MONTHS + r")\b", re.I),
    re.compile(r"\blast\s+(quarter|month|year|week)\b", re.I),
    re.compile(r"\bthis\s+(quarter|month|year|week)\b", re.I),
    re.compile(r"\b(q[1-4])\s+\d{4}\b", re.I),
    re.compile(r"\b\d{4}\b"),  # 4-digit years
    re.compile(r"\b\d{1,2}/\d{1,2}(/\d{2,4})?\b"),  # dates like 3/15/2026
]

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
            "SELECT sql FROM template_cache WHERE key = ?", (template_key,)
        ).fetchone()
        if row is not None:
            return "template", row[0]

        rows = conn.execute(
            "SELECT question, sql, embedding FROM semantic_cache WHERE role = ?", (role,)
        ).fetchall()
        if rows:
            import numpy as np

            query_vec = _get_embedder().encode([norm])[0]
            best_sql, best_score = None, -1.0
            for _q, sql, blob in rows:
                vec = np.frombuffer(blob, dtype="float32")
                score = float(
                    np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec) + 1e-9)
                )
                if score > best_score:
                    best_score, best_sql = score, sql
            if best_score >= SEMANTIC_CACHE_THRESHOLD:
                return "semantic", best_sql
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
        conn.execute(
            "INSERT INTO semantic_cache (role, question, sql, embedding, created_at) VALUES (?,?,?,?,?)",
            (role, question, sql, vec.tobytes(), now),
        )
        conn.commit()
    finally:
        conn.close()
