"""Base class and shared SSE chunk builders."""

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from config import settings


class AbstractScenario(ABC):
    """
    Each scenario implements `generate_chunks` for a given turn.

    turn=0  → first call (initial question)
    turn=1  → second call (after ask_user_reply), etc.
    """

    @abstractmethod
    async def generate_chunks(
        self,
        run_id: str,
        question: str,
        history: list[dict],
        turn: int,
    ) -> AsyncGenerator[str, None]:
        """Yield raw SSE lines: 'data: {...}\\n\\n'"""

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _sse(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    @staticmethod
    async def _delay() -> None:
        await asyncio.sleep(settings.chunk_delay)

    @classmethod
    async def _stream_text(cls, run_id: str, question_id: str, text: str) -> AsyncGenerator[str, None]:
        """Yield STREAMING chunks word-by-word."""
        words = text.split()
        for i, word in enumerate(words):
            chunk = word if i == len(words) - 1 else word + " "
            yield cls._sse({
                "response_type": "STREAMING",
                "uuid": run_id,
                "question_id": question_id,
                "chunk": chunk,
                "metadata": {},
            })
            await cls._delay()

    @classmethod
    def _final_response(cls, run_id: str, question_id: str, text: str, cost: float = 0.001) -> str:
        return cls._sse({
            "response_type": "RESPONSE",
            "uuid": run_id,
            "question_id": question_id,
            "chunk": text,
            "full_response": {
                "agent_id": "policy-expert",
                "run_id": run_id,
                "status": "done",
                "metadata": {},
                "stats": {"total_cost": cost},
            },
        })

    @classmethod
    def _ask_user_chunk(
        cls,
        run_id: str,
        question_id: str,
        question_text: str,
        operation_name: str,
        options: list[str],
        cost: float = 0.001,
    ) -> str:
        return cls._sse({
            "response_type": "ASK_USER_RESPONSE",
            "uuid": run_id,
            "question_id": question_id,
            "chunk": question_text,
            "full_response": {
                "agent_id": "policy-expert",
                "run_id": run_id,
                "status": "blocked",
                "metadata": {
                    "operation_name": operation_name,
                    "options": options,
                    "save_to_history": True,
                },
                "stats": {"total_cost": cost},
            },
        })

    @classmethod
    def _error_chunk(cls, run_id: str, question_id: str, message: str) -> str:
        return cls._sse({
            "response_type": "ERROR",
            "uuid": run_id,
            "question_id": question_id,
            "error": message,
        })

    @classmethod
    def _status_chunk(cls, run_id: str, question_id: str, status: str) -> str:
        # Backend reads chunk.get("status_data") and validates it as StatusData(stage=...)
        return cls._sse({
            "response_type": "STATUS",
            "uuid": run_id,
            "question_id": question_id,
            "status_data": {"stage": status},
        })
