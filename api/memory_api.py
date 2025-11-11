from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .database import get_session
from .models import Memory

router = APIRouter()
TZ_UTC = timezone.utc


class MemorySetPayload(BaseModel):
    key: str
    value: Dict[str, Any]
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    ttl_min: Optional[int] = None


class MemoryDeletePayload(BaseModel):
    key: str


def _is_active(record: Memory) -> bool:
    now = datetime.now(tz=TZ_UTC)
    if record.ttl_expires_at and record.ttl_expires_at <= now:
        return False
    if record.valid_from and record.valid_from > now:
        return False
    if record.valid_to and record.valid_to < now:
        return False
    return True


def _serialize(record: Memory) -> Dict[str, Any]:
    return {
        "key": record.key,
        "value": record.value_json,
        "valid_from": record.valid_from,
        "valid_to": record.valid_to,
        "ttl_expires_at": record.ttl_expires_at,
        "updated_at": record.updated_at,
    }


@router.get("/memory.get")
def memory_get(key: str, session: Session = Depends(get_session)):
    record = session.get(Memory, key)
    if not record or not _is_active(record):
        raise HTTPException(404, "Not found")
    return _serialize(record)


@router.get("/memory.list")
def memory_list(prefix: Optional[str] = None, session: Session = Depends(get_session)):
    query = select(Memory)
    if prefix:
        query = query.where(Memory.key.like(f"{prefix}%"))
    records = [r for r in session.exec(query).all() if _is_active(r)]
    return [_serialize(r) for r in records]


@router.post("/memory.set")
def memory_set(payload: MemorySetPayload, session: Session = Depends(get_session)):
    now = datetime.now(tz=TZ_UTC)
    record = session.get(Memory, payload.key)
    ttl_expires_at = None
    if payload.ttl_min is not None:
        if payload.ttl_min <= 0:
            raise HTTPException(400, "ttl_min must be > 0")
        ttl_expires_at = now + timedelta(minutes=payload.ttl_min)
    if record:
        current_value = record.value_json or {}
        if not isinstance(current_value, dict) or not isinstance(payload.value, dict):
            record.value_json = payload.value
        else:
            merged = {**current_value, **payload.value}
            record.value_json = merged
        record.valid_from = payload.valid_from or record.valid_from
        record.valid_to = payload.valid_to or record.valid_to
        record.ttl_expires_at = ttl_expires_at or record.ttl_expires_at
        record.updated_at = now
        session.add(record)
    else:
        record = Memory(
            key=payload.key,
            value_json=payload.value,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
            ttl_expires_at=ttl_expires_at,
            updated_at=now,
        )
        session.add(record)
    session.commit()
    return _serialize(record)


@router.post("/memory.delete")
def memory_delete(payload: MemoryDeletePayload, session: Session = Depends(get_session)):
    record = session.get(Memory, payload.key)
    if not record:
        raise HTTPException(404, "Not found")
    session.delete(record)
    session.commit()
    return {"status": "deleted"}
