"""
Admin endpoints — for test runners to control mock behaviour at runtime.

POST /admin/scenario          — set the active scenario for new conversations
POST /admin/reset             — reset all state (conversations + scenario)
GET  /admin/status            — inspect current state
DELETE /admin/conversation/{run_id} — reset a specific conversation
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import state
from scenarios import REGISTRY

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


class ScenarioRequest(BaseModel):
    name: str


@router.post("/scenario")
async def set_scenario(body: ScenarioRequest) -> dict:
    if body.name not in REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario {body.name!r}. Available: {list(REGISTRY)}",
        )
    state.set_active_scenario(body.name)
    logger.info("admin: active scenario set to %r", body.name)
    return {"active_scenario": body.name}


@router.post("/reset")
async def reset_all() -> dict:
    state.reset_all()
    logger.info("admin: full state reset")
    return {"status": "reset", "active_scenario": state.get_active_scenario()}


@router.get("/status")
async def get_status() -> dict:
    return {
        "active_scenario": state.get_active_scenario(),
        "available_scenarios": list(REGISTRY),
    }


@router.delete("/conversation/{run_id}")
async def delete_conversation(run_id: str) -> dict:
    state.reset_conversation(run_id)
    return {"status": "deleted", "run_id": run_id}
