import asyncio
from collections.abc import AsyncGenerator

from config import settings
from scenarios.base import AbstractScenario


class ErrorScenario(AbstractScenario):
    """Always returns an ERROR chunk after a short delay."""

    MESSAGE = "Agent execution failed: internal error while processing the policy request."

    async def generate_chunks(
        self,
        run_id: str,
        question: str,
        history: list[dict],
        turn: int,
    ) -> AsyncGenerator[str, None]:
        question_id = f"{run_id}-q{turn}"
        yield self._status_chunk(run_id, question_id, "Processing...")
        await asyncio.sleep(settings.ask_user_delay)
        yield self._error_chunk(run_id, question_id, self.MESSAGE)
