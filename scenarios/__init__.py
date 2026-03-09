from scenarios.ask_user_chained import AskUserChainedScenario
from scenarios.ask_user_single import AskUserSingleScenario
from scenarios.base import AbstractScenario
from scenarios.error_scenario import ErrorScenario
from scenarios.simple_response import SimpleResponseScenario

REGISTRY: dict[str, type[AbstractScenario]] = {
    "simple_response": SimpleResponseScenario,
    "ask_user_single": AskUserSingleScenario,
    "ask_user_chained": AskUserChainedScenario,
    "error": ErrorScenario,
}


def get_scenario(name: str) -> AbstractScenario:
    cls = REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown scenario: {name!r}. Available: {list(REGISTRY)}")
    return cls()
