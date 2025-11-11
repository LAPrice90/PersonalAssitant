from typing import Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from .database import get_session
from .models import Memory

router = APIRouter()

DEFAULT_COLORS = {
    "meal": "#7FB069",
    "prep": "#B5D99C",
    "travel": "#7AA5D2",
    "work": "#4C78A8",
    "skill": "#C44E52",
    "break": "#F2C14E",
    "family": "#9B59B6",
    "errand": "#E67E22",
    "sleep": "#95A5A6",
}

MEMORY_KEY = "colors:map"


class ColorMapResponse(BaseModel):
    colors: Dict[str, str]


class ColorMapUpdate(BaseModel):
    colors: Dict[str, str]


def ensure_default_colors(session: Session | None = None) -> None:
    close_session = False
    if session is None:
        from .database import session_scope

        close_session = True
        ctx = session_scope()
        session = ctx.__enter__()
    try:
        record = session.get(Memory, MEMORY_KEY)
        if not record:
            record = Memory(key=MEMORY_KEY, value_json={"colors": DEFAULT_COLORS})
            session.add(record)
            session.commit()
    finally:
        if close_session:
            ctx.__exit__(None, None, None)


@router.get("/colors.map", response_model=ColorMapResponse)
def colors_map(session: Session = Depends(get_session)):
    record = session.get(Memory, MEMORY_KEY)
    if not record:
        ensure_default_colors(session)
        record = session.get(Memory, MEMORY_KEY)
    return ColorMapResponse(colors=record.value_json.get("colors", DEFAULT_COLORS))


@router.post("/colors.map", response_model=ColorMapResponse)
def colors_update(payload: ColorMapUpdate, session: Session = Depends(get_session)):
    record = session.get(Memory, MEMORY_KEY)
    if not record:
        record = Memory(key=MEMORY_KEY, value_json={"colors": payload.colors})
    else:
        record.value_json = {"colors": payload.colors}
    session.add(record)
    session.commit()
    return ColorMapResponse(colors=record.value_json["colors"])
