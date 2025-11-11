import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlmodel import Field, SQLModel, create_engine, Session, select

API_KEY = os.getenv("API_BEARER_KEY", "replace-me")
TZ_UTC = timezone.utc


def require_bearer(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    if token != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid token")


app = FastAPI(title="Luke Calendar API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


class Event(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    attendees_csv: Optional[str] = None
    description: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, index=True, unique=False)


class EventCreate(BaseModel):
    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    attendees: Optional[List[EmailStr]] = None
    description: Optional[str] = None
    idempotency_key: Optional[str] = None


class EventUpdate(BaseModel):
    id: str
    title: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    location: Optional[str] = None
    attendees: Optional[List[EmailStr]] = None
    description: Optional[str] = None


class BusyBlock(BaseModel):
    start: datetime
    end: datetime


class FreeBusyResponse(BaseModel):
    busy: List[BusyBlock]


class SlotsResponse(BaseModel):
    slots: List[BusyBlock]


engine = create_engine("sqlite:///calendar.db")
SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as s:
        yield s


def overlap(a_start, a_end, b_start, b_end) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def list_busy(session: Session, start: datetime, end: datetime) -> List[BusyBlock]:
    q = select(Event).where(
        Event.start < end,
        Event.end > start
    )
    rows = session.exec(q).all()
    return [BusyBlock(start=e.start, end=e.end) for e in rows]


def round_up(dt: datetime, minutes: int) -> datetime:
    discard = timedelta(minutes=dt.minute % minutes, seconds=dt.second, microseconds=dt.microsecond)
    if discard == timedelta(0):
        return dt.replace(second=0, microsecond=0)
    return (dt - discard + timedelta(minutes=minutes)).replace(second=0, microsecond=0)


@app.get("/availability.freebusy", response_model=FreeBusyResponse, dependencies=[Depends(require_bearer)])
def freebusy(start: datetime = Query(...), end: datetime = Query(...), session: Session = Depends(get_session)):
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(400, "Use ISO 8601 with timezone (UTC preferred)")
    return FreeBusyResponse(busy=list_busy(session, start.astimezone(TZ_UTC), end.astimezone(TZ_UTC)))


@app.get("/availability.find_slots", response_model=SlotsResponse, dependencies=[Depends(require_bearer)])
def find_slots(
    duration_min: int = Query(..., ge=5),
    window_start: datetime = Query(...),
    window_end: datetime = Query(...),
    round_to_min: int = Query(30, ge=5),
    buffer_min: int = Query(5, ge=0),
    session: Session = Depends(get_session),
):
    if window_start.tzinfo is None or window_end.tzinfo is None:
        raise HTTPException(400, "Use ISO 8601 with timezone")
    ws = window_start.astimezone(TZ_UTC)
    we = window_end.astimezone(TZ_UTC)
    dur = timedelta(minutes=duration_min)
    buffer_td = timedelta(minutes=buffer_min)

    busy = sorted(list_busy(session, ws, we), key=lambda b: b.start)
    t = round_up(ws, round_to_min)
    slots: List[BusyBlock] = []

    while t + dur <= we:
        candidate_start = t
        candidate_end = t + dur
        blocked = False
        for b in busy:
            b_start = b.start - buffer_td
            b_end = b.end + buffer_td
            if overlap(candidate_start, candidate_end, b_start, b_end):
                blocked = True
                t = max(t, b.end + buffer_td)
                t = round_up(t, round_to_min)
                break
        if not blocked:
            slots.append(BusyBlock(start=candidate_start, end=candidate_end))
            t = round_up(candidate_end + buffer_td, round_to_min)
    return SlotsResponse(slots=slots)


@app.post("/events.create", dependencies=[Depends(require_bearer)])
def events_create(payload: EventCreate, session: Session = Depends(get_session)):
    if payload.idempotency_key:
        existing = session.exec(select(Event).where(Event.idempotency_key == payload.idempotency_key)).first()
        if existing:
            return {"id": existing.id, "htmlLink": f"https://calendar.local/event/{existing.id}"}

    busy = list_busy(session, payload.start.astimezone(TZ_UTC), payload.end.astimezone(TZ_UTC))
    for b in busy:
        if overlap(payload.start, payload.end, b.start, b.end):
            raise HTTPException(409, "Time conflict – choose another slot")

    ev = Event(
        title=payload.title,
        start=payload.start.astimezone(TZ_UTC),
        end=payload.end.astimezone(TZ_UTC),
        location=payload.location,
        attendees_csv=",".join(payload.attendees) if payload.attendees else None,
        description=payload.description,
        idempotency_key=payload.idempotency_key,
    )
    session.add(ev)
    session.commit()
    return {"id": ev.id, "htmlLink": f"https://calendar.local/event/{ev.id}"}


@app.post("/events.update", dependencies=[Depends(require_bearer)])
def events_update(payload: EventUpdate, session: Session = Depends(get_session)):
    ev = session.get(Event, payload.id)
    if not ev:
        raise HTTPException(404, "Not found")

    new_start = payload.start.astimezone(TZ_UTC) if payload.start else ev.start
    new_end = payload.end.astimezone(TZ_UTC) if payload.end else ev.end
    busy = list_busy(session, new_start, new_end)
    for b in busy:
        if b.start == ev.start and b.end == ev.end:
            continue
        if overlap(new_start, new_end, b.start, b.end):
            raise HTTPException(409, "Time conflict – choose another slot")

    ev.title = payload.title or ev.title
    ev.start = new_start
    ev.end = new_end
    ev.location = payload.location or ev.location
    ev.attendees_csv = ",".join(payload.attendees) if payload.attendees is not None else ev.attendees_csv
    ev.description = payload.description or ev.description
    session.add(ev)
    session.commit()
    return {"id": ev.id, "htmlLink": f"https://calendar.local/event/{ev.id}"}


@app.post("/events.delete", dependencies=[Depends(require_bearer)])
def events_delete(data: dict, session: Session = Depends(get_session)):
    ev_id = data.get("id")
    if not ev_id:
        raise HTTPException(400, "id required")
    ev = session.get(Event, ev_id)
    if not ev:
        return {"status": "ok"}
    session.delete(ev)
    session.commit()
    return {"status": "ok"}
