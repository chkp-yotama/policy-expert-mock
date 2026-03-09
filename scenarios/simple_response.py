from collections.abc import AsyncGenerator

from scenarios.base import AbstractScenario


class SimpleResponseScenario(AbstractScenario):
    """
    Always returns a plain RESPONSE.
    Streams a few intermediate STREAMING chunks, then the full answer.
    """

    ANSWER = (
        "I've analyzed your request. "
        "The policy has been reviewed and no immediate action is required. "
        "All rules are compliant with the current security posture."
    )

    async def generate_chunks(
        self,
        run_id: str,
        question: str,
        history: list[dict],
        turn: int,
    ) -> AsyncGenerator[str, None]:
        question_id = f"{run_id}-q"

        yield self._status_chunk(run_id, question_id, "Analyzing request...")
        await self._delay()

        async for chunk in self._stream_text(run_id, question_id, self.ANSWER):
            yield chunk

        yield self._final_response(run_id, question_id, self.ANSWER)
