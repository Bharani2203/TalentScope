"""FastAPI router for the Supervisor Agent Assistant.

Exposes:
- POST /api/assistant/chat: Full JSON conversation response.
- POST /api/assistant/stream: Server-Sent Events (SSE) streaming for real-time tool calls and answer tokens.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.services.supervisor_agent import (
    ChatMessage,
    SupervisorResponse,
    UserContext,
    run_supervisor_agent,
    stream_supervisor_agent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    user_context: UserContext = Field(default_factory=UserContext)


@router.post("/chat", response_model=SupervisorResponse)
async def supervisor_chat(request: ChatRequest):
    """Execute unified Supervisor Agent chat turn across intelligence tools with clean error handling."""
    try:
        return await run_supervisor_agent(
            messages=request.messages,
            user_context=request.user_context,
        )
    except Exception as exc:
        logger.error("Gemini API key is missing or invalid.")
        logger.error("Supervisor chat failed with exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Gemini API key is missing or invalid.",
                "message": "Unable to connect to the Gemini AI service. Please check API keys.",
                "detail": str(exc),
            },
        )


@router.post("/stream")
async def supervisor_stream(request: ChatRequest) -> StreamingResponse:
    """Stream Supervisor Agent execution events via Server-Sent Events (SSE)."""

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in stream_supervisor_agent(request.messages, request.user_context):
                event_name = event.get("event", "message")
                data_json = json.dumps(event.get("data", {}))
                yield f"event: {event_name}\ndata: {data_json}\n\n"
        except Exception as exc:
            logger.error("Error during supervisor stream: %s", exc)
            err_json = json.dumps({"error": str(exc)})
            yield f"event: error\ndata: {err_json}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

