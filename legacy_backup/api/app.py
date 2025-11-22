import os
from datetime import timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import memory_api, planner_api, pantry_api, recipes_api, shopping_api, skills_api, calendar_api, colors_api
from .database import init_db

API_KEY = os.getenv("API_BEARER_KEY", "replace-me")
TZ_UTC = timezone.utc

app = FastAPI(title="Luke Calendar API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


def require_bearer(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    if token != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid token")


def boot() -> None:
    init_db()
    colors_api.ensure_default_colors()


boot()

app.include_router(calendar_api.router, dependencies=[Depends(require_bearer)])
app.include_router(memory_api.router, dependencies=[Depends(require_bearer)])
app.include_router(planner_api.router, dependencies=[Depends(require_bearer)])
app.include_router(recipes_api.router, dependencies=[Depends(require_bearer)])
app.include_router(pantry_api.router, dependencies=[Depends(require_bearer)])
app.include_router(shopping_api.router, dependencies=[Depends(require_bearer)])
app.include_router(skills_api.router, dependencies=[Depends(require_bearer)])
app.include_router(colors_api.router, dependencies=[Depends(require_bearer)])
