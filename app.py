# app.py  –  Luke Calendar API  (full working version)

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlmodel import Field, SQLModel, create_engine, Session, select
import uuid
import pytz
import os

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------
API_KEY = os.getenv("API_BEARER_KEY", "supersecret")
TZ_UTC = timezone.utc
LONDON = pytz.timezone("Europe/London")

def require_bearer(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    if token != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid token")

app = FastAPI(title="Luke Calendar API")
security = HTTPBearer()


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description="Luke Calendar API",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    }
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method.setdefault("security", [{"BearerAuth": []}])
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# -------------------------------------------------------------------
# Database setup
# -------------------------------------------------------------------
engine = create_engine("sqlite:///calendar.db")
# -------------------------------------------------------------------
# Models
# -------------------------------------------------------------------
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

SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def overlap(a_start, a_end, b_start, b_end) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)

def list_busy(session: Session, start: datetime, end: datetime) -> List[BusyBlock]:
    q = select(Event).where(Event.start < end, Event.end > start)
    rows = session.exec(q).all()
    return [BusyBlock(start=e.start, end=e.end) for e in rows]

def ensure_tz(dt: datetime) -> datetime:
    """If datetime has no tz, assume Europe/London."""
    if dt.tzinfo:
        return dt.astimezone(TZ_UTC)
    return LONDON.localize(dt).astimezone(TZ_UTC)

# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------

@app.get("/time.now")
def time_now():
    now_utc = datetime.now(TZ_UTC)
    now_local = now_utc.astimezone(LONDON)
    offset_minutes = int(now_local.utcoffset().total_seconds() // 60)
    return {
        "utc": now_utc.isoformat().replace("+00:00", "Z"),
        "tz": "Europe/London",
        "local": now_local.isoformat(),
        "offset_minutes": offset_minutes
    }

@app.get("/availability.freebusy", response_model=FreeBusyResponse,
         dependencies=[Depends(require_bearer)])
def freebusy(start: datetime = Query(...), end: datetime = Query(...),
             session: Session = Depends(get_session)):
    start, end = ensure_tz(start), ensure_tz(end)
    return FreeBusyResponse(busy=list_busy(session, start, end))

@app.get("/events.list", dependencies=[Depends(require_bearer)])
def events_list(start: datetime = Query(...), end: datetime = Query(...),
                session: Session = Depends(get_session)):
    start, end = ensure_tz(start), ensure_tz(end)
    q = select(Event).where(Event.start < end, Event.end > start).order_by(Event.start)
    rows = session.exec(q).all()
    return [e.__dict__ for e in rows]

@app.post("/events.create", dependencies=[Depends(require_bearer)])
def events_create(payload: EventCreate, session: Session = Depends(get_session)):
    start, end = ensure_tz(payload.start), ensure_tz(payload.end)

    # idempotency
    if payload.idempotency_key:
        existing = session.exec(select(Event).where(
            Event.idempotency_key == payload.idempotency_key)).first()
        if existing:
            return {"id": existing.id, "htmlLink": f"https://calendar.local/event/{existing.id}"}

    # conflict detection
    for b in list_busy(session, start, end):
        if overlap(start, end, b.start, b.end):
            raise HTTPException(409, "Time conflict – choose another slot")

    ev = Event(
        title=payload.title, start=start, end=end,
        location=payload.location,
        attendees_csv=",".join(payload.attendees) if payload.attendees else None,
        description=payload.description, idempotency_key=payload.idempotency_key
    )
    session.add(ev)
    session.commit()
    return {"id": ev.id, "htmlLink": f"https://calendar.local/event/{ev.id}"}

@app.post("/events.update", dependencies=[Depends(require_bearer)])
def events_update(payload: EventUpdate, session: Session = Depends(get_session)):
    ev = session.get(Event, payload.id)
    if not ev:
        raise HTTPException(404, "Event not found")

    new_start = ensure_tz(payload.start) if payload.start else ev.start
    new_end = ensure_tz(payload.end) if payload.end else ev.end
    busy = list_busy(session, new_start, new_end)
    for b in busy:
        if b.start == ev.start and b.end == ev.end:
            continue
        if overlap(new_start, new_end, b.start, b.end):
            raise HTTPException(409, "Time conflict – choose another slot")

    ev.title = payload.title or ev.title
    ev.start, ev.end = new_start, new_end
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
        return {"status": "ok"}  # idempotent delete
    session.delete(ev)
    session.commit()
    return {"status": "ok"}

# -------------------------------------------------------------------
# Run
# -------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
