"""
GET /api/v1/agents

Returns a mock list of available agents so the backend's agent discovery works.
"""

from fastapi import APIRouter

router = APIRouter()

MOCK_AGENTS = [
    {
        "agent_id": "policy-expert",
        "name": "Policy Expert",
        "description": "Mock policy expert agent for integration testing",
        "agent_type": "langchain-1",
        "enabled": True,
    }
]


@router.get("/api/v1/agents")
async def list_agents() -> dict:
    return {"agents": MOCK_AGENTS}
