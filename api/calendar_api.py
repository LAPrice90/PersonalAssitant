from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from .database import get_session
from .models import Event

router = APIRouter()
TZ_UTC = timezone.utc


class BusyBlock(BaseModel):
    start: datetime
    end: datetime


class FreeBusyResponse(BaseModel):
    busy: List[BusyBlock]


class SlotsResponse(BaseModel):
    slots: List[BusyBlock]


class EventCreate(BaseModel):
    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    attendees: Optional[List[EmailStr]] = None
    description: Optional[str] = None
    idempotency_key: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    meta: Optional[Dict[str, object]] = None


class EventUpdate(BaseModel):
    id: str
    title: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    location: Optional[str] = None
    attendees: Optional[List[EmailStr]] = None
    description: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    meta: Optional[Dict[str, object]] = None


class EventOut(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    location: Optional[str]
    attendees: List[EmailStr]
    description: Optional[str]
    category: Optional[str]
    color: Optional[str]
    meta: Optional[Dict[str, object]]

    @classmethod
    def from_model(cls, event: Event) -> "EventOut":
        attendees = event.attendees_csv.split(",") if event.attendees_csv else []
        return cls(
            id=event.id,
            title=event.title,
            start=event.start,
            end=event.end,
            location=event.location,
            attendees=[EmailStr(a) for a in attendees if a],
            description=event.description,
            category=event.category,
            color=event.color,
            meta=event.meta_json,
        )


def _overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def _list_busy(session: Session, start: datetime, end: datetime) -> List[BusyBlock]:
    q = select(Event).where(Event.start < end, Event.end > start)
    rows = session.exec(q).all()
    return [BusyBlock(start=e.start, end=e.end) for e in rows]


def _round_up(dt: datetime, minutes: int) -> datetime:
    discard = timedelta(minutes=dt.minute % minutes, seconds=dt.second, microseconds=dt.microsecond)
    if discard == timedelta(0):
        return dt.replace(second=0, microsecond=0)
    return (dt - discard + timedelta(minutes=minutes)).replace(second=0, microsecond=0)


@router.get("/availability.freebusy", response_model=FreeBusyResponse)
def freebusy(
    start: datetime = Query(...),
    end: datetime = Query(...),
    session: Session = Depends(get_session),
):
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(400, "Use ISO 8601 with timezone (UTC preferred)")
    return FreeBusyResponse(busy=_list_busy(session, start.astimezone(TZ_UTC), end.astimezone(TZ_UTC)))


@router.get("/availability.find_slots", response_model=SlotsResponse)
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

    busy = sorted(_list_busy(session, ws, we), key=lambda b: b.start)
    t = _round_up(ws, round_to_min)
    slots: List[BusyBlock] = []

    while t + dur <= we:
        candidate_start = t
        candidate_end = t + dur
        blocked = False
        for b in busy:
            b_start = b.start - buffer_td
            b_end = b.end + buffer_td
            if _overlap(candidate_start, candidate_end, b_start, b_end):
                blocked = True
                t = max(t, b.end + buffer_td)
                t = _round_up(t, round_to_min)
                break
        if not blocked:
            slots.append(BusyBlock(start=candidate_start, end=candidate_end))
            t = _round_up(candidate_end + buffer_td, round_to_min)
    return SlotsResponse(slots=slots)


@router.get("/events.list", response_model=List[EventOut])
def events_list(
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    session: Session = Depends(get_session),
):
    query = select(Event)
    if start:
        if start.tzinfo is None:
            raise HTTPException(400, "Start must include timezone")
        query = query.where(Event.end >= start.astimezone(TZ_UTC))
    if end:
        if end.tzinfo is None:
            raise HTTPException(400, "End must include timezone")
        query = query.where(Event.start <= end.astimezone(TZ_UTC))
    query = query.order_by(Event.start)
    events = session.exec(query).all()
    return [EventOut.from_model(e) for e in events]


@router.post("/events.create")
def events_create(payload: EventCreate, session: Session = Depends(get_session)):
    if payload.idempotency_key:
        existing = session.exec(select(Event).where(Event.idempotency_key == payload.idempotency_key)).first()
        if existing:
            return {"id": existing.id, "htmlLink": f"https://calendar.local/event/{existing.id}"}

    busy = _list_busy(session, payload.start.astimezone(TZ_UTC), payload.end.astimezone(TZ_UTC))
    for b in busy:
        if _overlap(payload.start, payload.end, b.start, b.end):
            raise HTTPException(409, "Time conflict – choose another slot")

    ev = Event(
        title=payload.title,
        start=payload.start.astimezone(TZ_UTC),
        end=payload.end.astimezone(TZ_UTC),
        location=payload.location,
        attendees_csv=",".join(payload.attendees) if payload.attendees else None,
        description=payload.description,
        idempotency_key=payload.idempotency_key,
        category=payload.category,
        color=payload.color,
        meta_json=payload.meta,
    )
    session.add(ev)
    session.commit()
    return {"id": ev.id, "htmlLink": f"https://calendar.local/event/{ev.id}"}


@router.post("/events.update")
def events_update(payload: EventUpdate, session: Session = Depends(get_session)):
    ev = session.get(Event, payload.id)
    if not ev:
        raise HTTPException(404, "Not found")

    new_start = payload.start.astimezone(TZ_UTC) if payload.start else ev.start
    new_end = payload.end.astimezone(TZ_UTC) if payload.end else ev.end
    busy = _list_busy(session, new_start, new_end)
    for b in busy:
        if b.start == ev.start and b.end == ev.end:
            continue
        if _overlap(new_start, new_end, b.start, b.end):
            raise HTTPException(409, "Time conflict – choose another slot")

    ev.title = payload.title or ev.title
    ev.start = new_start
    ev.end = new_end
    ev.location = payload.location or ev.location
    if payload.attendees is not None:
        ev.attendees_csv = ",".join(payload.attendees)
    ev.description = payload.description or ev.description
    ev.category = payload.category or ev.category
    ev.color = payload.color or ev.color
    ev.meta_json = payload.meta if payload.meta is not None else ev.meta_json
    session.add(ev)
    session.commit()
    return {"id": ev.id, "htmlLink": f"https://calendar.local/event/{ev.id}"}
