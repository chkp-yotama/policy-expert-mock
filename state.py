"""
In-memory state for the mock server.

- active_scenario: name of the scenario to use for new conversations
- conversation_state: tracks per run_id state so multi-turn flows (ask_user) work correctly
"""

from dataclasses import dataclass, field

from config import settings


@dataclass
class ConversationState:
    scenario: str
    turn: int = 0  # incremented each time stream() is called for this run_id


_active_scenario: str = settings.default_scenario
_conversations: dict[str, ConversationState] = {}


def get_active_scenario() -> str:
    return _active_scenario


def set_active_scenario(name: str) -> None:
    global _active_scenario
    _active_scenario = name


def get_or_create_conversation(run_id: str) -> ConversationState:
    if run_id not in _conversations:
        _conversations[run_id] = ConversationState(scenario=_active_scenario)
    return _conversations[run_id]


def advance_turn(run_id: str) -> int:
    state = get_or_create_conversation(run_id)
    state.turn += 1
    return state.turn


def reset_conversation(run_id: str) -> None:
    _conversations.pop(run_id, None)


def reset_all() -> None:
    global _active_scenario
    _active_scenario = settings.default_scenario
    _conversations.clear()
