import asyncio
from collections.abc import AsyncGenerator

from config import settings
from scenarios.base import AbstractScenario


class AskUserSingleScenario(AbstractScenario):
    """
    turn=0: streams ASK_USER_RESPONSE — asks for confirmation.
    turn=1: streams RESPONSE — executes the action after user approved/rejected.
    """

    ASK_QUESTION = "Do you want to apply the proposed policy change? This will affect all network traffic on port 443."
    OPERATION = "apply_policy_change"
    OPTIONS = ["approve", "reject"]

    APPROVED_ANSWER = (
        "Policy change applied successfully. "
        "Outbound traffic on port 443 is now blocked for all endpoints in the selected scope."
    )
    REJECTED_ANSWER = "Policy change was cancelled. No changes were made to the current configuration."

    async def generate_chunks(
        self,
        run_id: str,
        question: str,
        history: list[dict],
        turn: int,
    ) -> AsyncGenerator[str, None]:
        question_id = f"{run_id}-q{turn}"

        if turn == 0:
            # First call — ask for confirmation
            yield self._status_chunk(run_id, question_id, "Evaluating policy impact...")
            await asyncio.sleep(settings.ask_user_delay)
            yield self._ask_user_chunk(
                run_id=run_id,
                question_id=question_id,
                question_text=self.ASK_QUESTION,
                operation_name=self.OPERATION,
                options=self.OPTIONS,
            )
        else:
            # Subsequent call — user replied, continue execution
            decision = self._extract_decision(history)
            answer = self.APPROVED_ANSWER if decision == "approve" else self.REJECTED_ANSWER

            yield self._status_chunk(run_id, question_id, "Processing your decision...")
            await self._delay()

            async for chunk in self._stream_text(run_id, question_id, answer):
                yield chunk

            yield self._final_response(run_id, question_id, answer)

    @staticmethod
    def _extract_decision(history: list[dict]) -> str:
        """Pull the last user message from history — that's the decision."""
        for entry in reversed(history):
            if entry.get("role") == "user":
                return entry.get("content", "").strip().lower()
        return "approve"
