# policy-expert-mock

Mock Agent Platform for the **policy-expert** agent.
Implements the SSE streaming endpoint that `console-one-backend` calls via `AgentRunnerClient.stream()`.

Used for integration testing the full frontend ↔ backend ↔ agent flow without a real agent.

---

## Setup

```bash
uv venv --python 3.12
uv pip install -e . --python .venv/bin/python
```

## Run

```bash
python main.py
# or
uvicorn main:app --port 8080 --reload
```

Environment variables (prefix `MOCK_`):

| Variable | Default | Description |
|---|---|---|
| `MOCK_PORT` | `8080` | Listen port |
| `MOCK_HOST` | `0.0.0.0` | Listen host |
| `MOCK_DEFAULT_SCENARIO` | `simple_response` | Scenario for new conversations |
| `MOCK_CHUNK_DELAY` | `0.05` | Seconds between streaming chunks |
| `MOCK_ASK_USER_DELAY` | `0.3` | Seconds before ask-user question |

---

## Point the backend at the mock

Set the agent runner URL to this server before starting `console-one-backend`:

```bash
# example — adjust to your actual env var name
AGENT_RUNNER_URL_TEMPLATE=http://localhost:8080 uvicorn app.main:app ...
```

---

## Available scenarios

| Name | Description |
|---|---|
| `simple_response` | Streams a plain answer — no confirmation needed |
| `ask_user_single` | One confirmation round: approve → action applied, reject → cancelled |
| `ask_user_chained` | Two confirmation rounds before final action |
| `error` | Immediately returns an ERROR chunk |

---

## Admin API

Control the mock at runtime from a test runner.

### Set active scenario

```bash
curl -X POST http://localhost:8080/admin/scenario \
  -H 'Content-Type: application/json' \
  -d '{"name": "ask_user_single"}'
```

### Reset all state

```bash
curl -X POST http://localhost:8080/admin/reset
```

### Check status

```bash
curl http://localhost:8080/admin/status
```

### Delete a specific conversation

```bash
curl -X DELETE http://localhost:8080/admin/conversation/{run_id}
```

---

## How the ask_user flow works

```
1. Backend calls POST /api/v1/agent/stream  (turn 0)
   → mock returns ASK_USER_RESPONSE chunk

2. Backend forwards to frontend via WebSocket

3. User decides → frontend sends ask_user_reply to backend

4. Backend calls POST /api/v1/agent/stream again with full history  (turn 1)
   → mock sees turn=1, reads decision from history, returns RESPONSE chunk
```

The mock tracks turns per `run_id` in memory.
Each new `run_id` starts at turn 0 with the currently active scenario.

---

## Project structure

```
policy-expert-mock/
├── main.py                     # FastAPI app + entry point
├── config.py                   # Settings (pydantic-settings)
├── state.py                    # In-memory conversation state
├── scenarios/
│   ├── base.py                 # AbstractScenario + SSE chunk builders
│   ├── simple_response.py
│   ├── ask_user_single.py
│   ├── ask_user_chained.py
│   └── error_scenario.py
└── routers/
    ├── stream.py               # POST /api/v1/agent/stream  (SSE)
    ├── agents.py               # GET  /api/v1/agents
    └── admin.py                # POST /admin/scenario, /admin/reset, etc.
```