"""
POST /api/v1/agent/stream

Mimics the AgentRunner SSE streaming endpoint.
The backend sends AgentRequest JSON and reads SSE chunks.
"""

import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

import state
from scenarios import get_scenario

logger = logging.getLogger(__name__)
router = APIRouter()


async def _event_stream(run_id: str, question: str, history: list[dict], turn: int) -> AsyncGenerator[bytes, None]:
    scenario_name = state.get_or_create_conversation(run_id).scenario
    scenario = get_scenario(scenario_name)
    logger.info("stream: run_id=%s scenario=%s turn=%d question=%r", run_id, scenario_name, turn, question[:80])

    async for chunk in scenario.generate_chunks(run_id, question, history, turn):
        yield chunk.encode()


@router.post("/api/v1/agent/stream")
async def agent_stream(request: Request) -> StreamingResponse:
    body = await request.json()

    chat_request = body.get("chat_request", {})
    run_id = chat_request.get("uuid", "unknown-run")
    question = chat_request.get("question", "")
    history: list[dict] = body.get("history", [])

    # Ensure conversation state exists before advancing turn
    state.get_or_create_conversation(run_id)
    turn = state.advance_turn(run_id) - 1  # first call → turn 0

    return StreamingResponse(
        _event_stream(run_id, question, history, turn),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
