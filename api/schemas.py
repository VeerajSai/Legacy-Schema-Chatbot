"""Pydantic request/response models for the /chat endpoint. Thin mirror of
contracts.types.PipelineContext -- only the fields the outward-facing API
needs to expose."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str
    user_id: str = "anonymous"
    role: str = "sales_analyst"
    conversation: list[dict] | None = None


class ChatResponse(BaseModel):
    answer: str | None = None
    sql: str | None = None
    row_count: int = 0
    truncated: bool = False
    tables_used: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    blocked_reason: str | None = None
    cache_hit: str | None = None


class HealthResponse(BaseModel):
    status: str
