"""Stage 11: structured audit/metrics log (doc section 4 stage 11 / section 8
security model's audit-log requirement)."""
from __future__ import annotations

import json
import time

from config.settings import PIPELINE_LOG_PATH
from contracts.types import PipelineContext


def log_event(ctx: PipelineContext) -> None:
    PIPELINE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": time.time(),
        "request_id": ctx.request_id,
        "role": ctx.role,
        "cache_hit": ctx.cache_hit,
        "retries": ctx.retries,
        "tokens_used": ctx.tokens_used,
        "stage_timings_ms": ctx.stage_timings_ms,
        "success": bool(ctx.execution.success) if ctx.execution else (ctx.blocked_reason is None and ctx.clarification_question is None),
        "error": ctx.execution.error if ctx.execution else None,
        "blocked_reason": ctx.blocked_reason,
    }
    with open(PIPELINE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
