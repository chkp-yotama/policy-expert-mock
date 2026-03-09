import asyncio
from collections.abc import AsyncGenerator

from config import settings
from scenarios.base import AbstractScenario


class AskUserChainedScenario(AbstractScenario):
    """
    Two confirmation rounds before final action.

    turn=0: ASK_USER_RESPONSE — "Do you want to proceed?"
    turn=1: ASK_USER_RESPONSE — "Are you sure? This is irreversible."
    turn=2: RESPONSE          — final result
    """

    QUESTIONS = [
        {
            "text": "I'm about to modify the firewall policy to block port 443 outbound. Do you want to proceed?",
            "operation": "initiate_policy_change",
            "options": ["approve", "reject"],
        },
        {
            "text": (
                "This will affect all 47 endpoints in your production scope. "
                "This change is irreversible without a manual rollback. Are you sure?"
            ),
            "operation": "confirm_irreversible_change",
            "options": ["confirm", "cancel"],
        },
    ]

    FINAL_ANSWER = (
        "Firewall policy updated. "
        "Port 443 outbound traffic is now blocked for all 47 production endpoints. "
        "A rollback plan has been saved to your audit log."
    )
    CANCELLED_ANSWER = "Operation cancelled. No changes were applied."

    async def generate_chunks(
        self,
        run_id: str,
        question: str,
        history: list[dict],
        turn: int,
    ) -> AsyncGenerator[str, None]:
        question_id = f"{run_id}-q{turn}"

        if turn < len(self.QUESTIONS):
            q = self.QUESTIONS[turn]
            yield self._status_chunk(run_id, question_id, f"Step {turn + 1} of {len(self.QUESTIONS) + 1}...")
            await asyncio.sleep(settings.ask_user_delay)
            yield self._ask_user_chunk(
                run_id=run_id,
                question_id=question_id,
                question_text=q["text"],
                operation_name=q["operation"],
                options=q["options"],
            )
        else:
            # All confirmations done — check if any rejection happened
            cancelled = self._was_cancelled(history)
            answer = self.CANCELLED_ANSWER if cancelled else self.FINAL_ANSWER

            yield self._status_chunk(run_id, question_id, "Applying changes...")
            await self._delay()

            async for chunk in self._stream_text(run_id, question_id, answer):
                yield chunk

            yield self._final_response(run_id, question_id, answer)

    @staticmethod
    def _was_cancelled(history: list[dict]) -> bool:
        """Returns True if any user decision was a rejection."""
        negative = {"reject", "cancel", "no"}
        for entry in history:
            if entry.get("role") == "user" and entry.get("content", "").strip().lower() in negative:
                return True
        return False
