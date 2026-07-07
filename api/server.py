"""FastAPI wrapper around pipeline.orchestrator.answer_question.
Run with: uvicorn api.server:app --reload
"""
from __future__ import annotations

from fastapi import FastAPI

from api.schemas import ChatRequest, ChatResponse, HealthResponse

app = FastAPI(title="Schemantic API")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    from pipeline.orchestrator import answer_question  # imported lazily: pipeline lands separately

    ctx = answer_question(
        req.question, user_id=req.user_id, role=req.role, conversation=req.conversation,
    )
    execution = ctx.execution
    return ChatResponse(
        answer=ctx.answer,
        sql=ctx.sql_candidate,
        row_count=execution.row_count if execution else 0,
        truncated=execution.truncated if execution else False,
        tables_used=list(ctx.graph.all_tables) if ctx.graph else [],
        clarification_question=ctx.clarification_question,
        blocked_reason=ctx.blocked_reason,
        cache_hit=ctx.cache_hit,
    )
