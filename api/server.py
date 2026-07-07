"""FastAPI wrapper around pipeline.orchestrator.answer_question.
Run with: uvicorn api.server:app --reload
"""
from __future__ import annotations

import json
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from api.schemas import ChatRequest, ChatResponse, HealthResponse
from config.settings import PIPELINE_LOG_PATH

app = FastAPI(title="Legacy Schema Chatbot API")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    from pipeline.orchestrator import answer_question  # imported lazily: pipeline lands separately

    try:
        ctx = answer_question(
            req.question, user_id=req.user_id, role=req.role, conversation=req.conversation,
        )
    except Exception as e:
        # ponytail: no full PipelineContext exists when the pipeline crashes
        # mid-flight, so write a minimal fallback line straight to the same
        # audit log instead of building one; upgrade to log_event(ctx) if a
        # partial ctx ever becomes available at the crash site.
        PIPELINE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": time.time(),
            "role": req.role,
            "question": req.question,
            "success": False,
            "error": str(e),
        }
        with open(PIPELINE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return JSONResponse(content={"error": "internal error processing request"}, status_code=500)

    execution = ctx.execution
    response = ChatResponse(
        answer=ctx.answer,
        sql=ctx.sql_candidate,
        row_count=execution.row_count if execution else 0,
        truncated=execution.truncated if execution else False,
        tables_used=list(ctx.graph.all_tables) if ctx.graph else [],
        clarification_question=ctx.clarification_question,
        blocked_reason=ctx.blocked_reason,
        cache_hit=ctx.cache_hit,
    )
    status_code = 200
    if response.blocked_reason:
        status_code = 403
    elif response.clarification_question:
        status_code = 422
    return JSONResponse(content=response.model_dump(), status_code=status_code)
