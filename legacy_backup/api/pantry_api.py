from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from .database import get_session
from .models import PantryItem

router = APIRouter()


class PantryUpsertRequest(BaseModel):
    name: str
    qty: float = Field(ge=0)
    unit: Optional[str] = None
    category: Optional[str] = None
    opened_at: Optional[date] = None
    use_by: Optional[date] = None
    best_before: Optional[date] = None
    notes: Optional[str] = None


class PantryResponse(BaseModel):
    id: str
    name: str
    quantity: float
    unit: Optional[str]
    category: Optional[str]
    opened_at: Optional[date]
    use_by: Optional[date]
    best_before: Optional[date]
    notes: Optional[str]
    updated_at: datetime
    unsafe: bool = False

    @classmethod
    def from_model(cls, item: PantryItem) -> "PantryResponse":
        unsafe = False
        today = date.today()
        if item.use_by and item.use_by < today:
            unsafe = True
        return cls(
            id=item.id,
            name=item.name,
            quantity=item.quantity,
            unit=item.unit,
            category=item.category,
            opened_at=item.opened_at,
            use_by=item.use_by,
            best_before=item.best_before,
            notes=item.notes,
            updated_at=item.updated_at,
            unsafe=unsafe,
        )


@router.post("/pantry.add_or_update", response_model=PantryResponse)
def pantry_add_or_update(payload: PantryUpsertRequest, session: Session = Depends(get_session)):
    lowered = payload.name.strip().lower()
    existing = session.exec(select(PantryItem).where(func.lower(PantryItem.name) == lowered)).first()
    now = datetime.now(timezone.utc)
    if existing:
        existing.quantity = payload.qty
        existing.unit = payload.unit
        existing.category = payload.category
        existing.opened_at = payload.opened_at
        existing.use_by = payload.use_by
        existing.best_before = payload.best_before
        existing.notes = payload.notes
        existing.updated_at = now
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return PantryResponse.from_model(existing)
    item = PantryItem(
        name=payload.name.strip(),
        quantity=payload.qty,
        unit=payload.unit,
        category=payload.category,
        opened_at=payload.opened_at,
        use_by=payload.use_by,
        best_before=payload.best_before,
        notes=payload.notes,
        updated_at=now,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return PantryResponse.from_model(item)


@router.get("/pantry.expiring", response_model=Dict[str, Dict[str, Optional[str]]])
def pantry_expiring(within_days: int = Query(3, ge=0), session: Session = Depends(get_session)):
    today = date.today()
    horizon = today + timedelta(days=within_days)
    items = session.exec(select(PantryItem)).all()
    expiring = {}
    for item in items:
        if item.use_by and item.use_by <= horizon:
            expiring[item.id] = {
                "name": item.name,
                "use_by": item.use_by.isoformat(),
                "best_before": item.best_before.isoformat() if item.best_before else None,
                "unsafe": item.use_by < today,
            }
        elif item.best_before and item.best_before <= horizon:
            expiring[item.id] = {
                "name": item.name,
                "use_by": item.use_by.isoformat() if item.use_by else None,
                "best_before": item.best_before.isoformat(),
                "unsafe": False,
            }
    return expiring
