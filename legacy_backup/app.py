# app.py — Luke Assistant API (Calendar + Memory + Directory, size-safe)

import os, uuid, json
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pytz
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, EmailStr
from sqlmodel import Field, SQLModel, create_engine, Session, select

# ---------------------- Config ----------------------
API_KEY = os.getenv("API_BEARER_KEY", "supersecret")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///calendar.db")
LONDON = pytz.timezone("Europe/London")
TZ_UTC = timezone.utc
MAX_LIST_HOURS = 6  # guardrail for /events.list

def require_bearer(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1]
    if token != API_KEY:
        raise HTTPException(403, "Invalid token")

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)

# tighten SQLite a bit
with engine.connect() as conn:
    conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
    conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
    conn.exec_driver_sql("PRAGMA busy_timeout=5000;")

app = FastAPI(title="Luke Calendar API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Swagger Authorize button
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description="Luke Assistant API (time, calendar, memory, directory, equipment)",
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    for path in schema.get("paths", {}).values():
        for method in path.values():
            method.setdefault("security", [{"BearerAuth": []}])
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

# ---------------------- Models ----------------------
class Event(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    attendees_csv: Optional[str] = None
    description: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, index=True)

class Memory(SQLModel, table=True):
    key: str = Field(primary_key=True)  # e.g. "equipment/kitchen.json"
    value_json: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(TZ_UTC))

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

class MemorySet(BaseModel):
    key: str
    value: dict

class EquipmentBody(BaseModel):
    items: List[str]

class DirectoryPatch(BaseModel):
    value: dict  # shallow merge

SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as s:
        yield s

# ---------------------- Helpers ----------------------
def to_utc(dt: datetime) -> datetime:
    """Ensure dt is timezone-aware in UTC."""
    if dt.tzinfo:
        return dt.astimezone(TZ_UTC)
    return LONDON.localize(dt).astimezone(TZ_UTC)

def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)

def list_busy(session: Session, start: datetime, end: datetime) -> List[BusyBlock]:
    rows = session.exec(select(Event).where(Event.start < end, Event.end > start)).all()
    return [BusyBlock(start=e.start, end=e.end) for e in rows]

def mem_get(session: Session, key: str):
    row = session.get(Memory, key)
    return json.loads(row.value_json) if row else None

def mem_set(session: Session, key: str, value: dict):
    row = session.get(Memory, key)
    encoded = json.dumps(value)
    if row:
        row.value_json = encoded
        row.updated_at = datetime.now(TZ_UTC)
        session.add(row)
    else:
        session.add(Memory(key=key, value_json=encoded))
    session.commit()

def mem_list(session: Session, prefix: Optional[str] = None) -> List[str]:
    q = select(Memory.key).order_by(Memory.key)
    keys = [k for (k,) in session.exec(q)]
    return [k for k in keys if (prefix is None or k.startswith(prefix))]

def mem_delete(session: Session, key: str):
    row = session.get(Memory, key)
    if row:
        session.delete(row)
        session.commit()

# ---------------------- Health ----------------------
@app.get("/health")
def health():
    return {"ok": True}

# ---------------------- Time ----------------------
@app.get("/time.now")
def time_now():
    now_utc = datetime.now(TZ_UTC)
    now_local = now_utc.astimezone(LONDON)
    off_min = int(now_local.utcoffset().total_seconds() // 60)
    return {
        "utc": now_utc.isoformat().replace("+00:00", "Z"),
        "tz": "Europe/London",
        "local": now_local.isoformat(),
        "offset_minutes": off_min,
    }

# ---------------------- Calendar ----------------------
@app.get("/availability.freebusy", response_model=FreeBusyResponse, dependencies=[Depends(require_bearer)])
def freebusy(start: datetime = Query(...), end: datetime = Query(...), session: Session = Depends(get_session)):
    start_utc, end_utc = to_utc(start), to_utc(end)
    return FreeBusyResponse(busy=list_busy(session, start_utc, end_utc))

@app.get("/events.list", dependencies=[Depends(require_bearer)])
def events_list(
    start: datetime = Query(...),
    end: datetime = Query(...),
    session: Session = Depends(get_session),
):
    start_utc, end_utc = to_utc(start), to_utc(end)
    if (end_utc - start_utc).total_seconds() > MAX_LIST_HOURS * 3600:
        raise HTTPException(
            413,
            detail=f"Range too large; use /events.summary_day or <= {MAX_LIST_HOURS} hours",
        )
    rows = session.exec(
        select(Event).where(Event.start < end_utc, Event.end > start_utc).order_by(Event.start)
    ).all()
    return [e.__dict__ for e in rows]

@app.get("/events.summary_day", dependencies=[Depends(require_bearer)])
def events_summary_day(
    date: str = Query(..., description="YYYY-MM-DD"),
    session: Session = Depends(get_session),
):
    try:
        day = datetime.fromisoformat(date)
        if day.tzinfo is None:
            day = day.replace(tzinfo=TZ_UTC)
    except ValueError:
        raise HTTPException(400, "Invalid date; use YYYY-MM-DD")
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    rows = session.exec(
        select(Event).where(Event.start < end, Event.end > start).order_by(Event.start)
    ).all()
    return [
        {
            "id": e.id,
            "title": e.title,
            "start": e.start.isoformat().replace("+00:00", "Z"),
            "end": e.end.isoformat().replace("+00:00", "Z"),
        }
        for e in rows
    ]

@app.post("/events.create", dependencies=[Depends(require_bearer)])
def events_create(payload: EventCreate, session: Session = Depends(get_session)):
    start, end = to_utc(payload.start), to_utc(payload.end)
    # idempotency
    if payload.idempotency_key:
        existing = session.exec(
            select(Event).where(Event.idempotency_key == payload.idempotency_key)
        ).first()
        if existing:
            return {
                "id": existing.id,
                "start": existing.start.isoformat().replace("+00:00", "Z"),
                "end": existing.end.isoformat().replace("+00:00", "Z"),
            }
    # conflict check (small windows)
    for b in list_busy(session, start, end):
        if overlaps(start, end, b.start, b.end):
            raise HTTPException(409, "Time conflict – choose another slot")

    ev = Event(
        title=payload.title,
        start=start,
        end=end,
        location=payload.location,
        attendees_csv=",".join(payload.attendees) if payload.attendees else None,
        description=payload.description,
        idempotency_key=payload.idempotency_key,
    )
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return {
        "id": ev.id,
        "start": ev.start.isoformat().replace("+00:00", "Z"),
        "end": ev.end.isoformat().replace("+00:00", "Z"),
    }

@app.post("/events.update", dependencies=[Depends(require_bearer)])
def events_update(payload: EventUpdate, session: Session = Depends(get_session)):
    ev = session.get(Event, payload.id)
    if not ev:
        raise HTTPException(404, "Event not found")

    new_start = to_utc(payload.start) if payload.start else ev.start
    new_end = to_utc(payload.end) if payload.end else ev.end
    for b in list_busy(session, new_start, new_end):
        if b.start == ev.start and b.end == ev.end:
            continue
        if overlaps(new_start, new_end, b.start, b.end):
            raise HTTPException(409, "Time conflict – choose another slot")

    ev.title = payload.title or ev.title
    ev.start, ev.end = new_start, new_end
    ev.location = payload.location or ev.location
    ev.attendees_csv = (
        ",".join(payload.attendees) if payload.attendees is not None else ev.attendees_csv
    )
    ev.description = payload.description or ev.description
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return {
        "id": ev.id,
        "start": ev.start.isoformat().replace("+00:00", "Z"),
        "end": ev.end.isoformat().replace("+00:00", "Z"),
    }

@app.post("/events.delete", dependencies=[Depends(require_bearer)])
def events_delete(data: dict, session: Session = Depends(get_session)):
    ev_id = data.get("id")
    if not ev_id:
        raise HTTPException(400, "id required")
    ev = session.get(Event, ev_id)
    if ev:
        session.delete(ev)
        session.commit()
    return {"status": "ok"}

# ---------------------- Memory ----------------------
@app.post("/memory.set", dependencies=[Depends(require_bearer)])
def memory_set(payload: MemorySet, session: Session = Depends(get_session)):
    mem_set(session, payload.key, payload.value)
    return {"status": "ok", "key": payload.key}

@app.get("/memory.get", dependencies=[Depends(require_bearer)])
def memory_get(key: str = Query(...), session: Session = Depends(get_session)):
    val = mem_get(session, key)
    if val is None:
        raise HTTPException(404, "Not found")
    return {"key": key, "value": val}

@app.get("/memory.list", dependencies=[Depends(require_bearer)])
def memory_keys(prefix: Optional[str] = Query(None), session: Session = Depends(get_session)):
    return {"keys": mem_list(session, prefix)}

@app.post("/memory.delete", dependencies=[Depends(require_bearer)])
def memory_del(payload: MemorySet, session: Session = Depends(get_session)):
    mem_delete(session, payload.key)
    return {"status": "ok"}

# ---------------------- Equipment ----------------------
@app.post("/equipment.set_list", dependencies=[Depends(require_bearer)])
def equipment_set_list(body: EquipmentBody, session: Session = Depends(get_session)):
    mem_set(session, "equipment/kitchen.json", {"items": body.items})
    return {"status": "ok"}

@app.get("/equipment.get_list", dependencies=[Depends(require_bearer)])
def equipment_get_list(session: Session = Depends(get_session)):
    return mem_get(session, "equipment/kitchen.json") or {"items": []}

# ---------------------- Directory ----------------------
DEFAULT_DIRECTORY = {
    "_v": 1,
    "calendar": {"create": "/events.create", "list": "/events.list"},
    "equipment": {"set": "/equipment.set_list", "get": "/equipment.get_list"},
    "memory": {"set": "/memory.set", "get": "/memory.get", "list": "/memory.list"},
}

@app.get("/directory.get", dependencies=[Depends(require_bearer)])
def directory_get(session: Session = Depends(get_session)):
    val = mem_get(session, "registry/directory.json")
    if not val:
        mem_set(session, "registry/directory.json", DEFAULT_DIRECTORY)
        val = DEFAULT_DIRECTORY
    return {"key": "registry/directory.json", "value": val}

@app.post("/directory.patch", dependencies=[Depends(require_bearer)])
def directory_patch(payload: DirectoryPatch, session: Session = Depends(get_session)):
    cur = mem_get(session, "registry/directory.json") or DEFAULT_DIRECTORY
    new_val = {**cur, **payload.value}
    mem_set(session, "registry/directory.json", new_val)
    return {"status": "ok", "value": new_val}

# ---------------------- Run (local) ----------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
