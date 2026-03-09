import logging
import logging.config

import uvicorn
from fastapi import FastAPI

from config import settings
from routers import admin, agents, stream

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Policy Expert Mock",
    description="Mock Agent Platform for policy-expert integration testing",
    version="0.1.0",
)

app.include_router(stream.router)
app.include_router(agents.router)
app.include_router(admin.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def main() -> None:
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
