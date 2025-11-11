import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


class Event(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    attendees_csv: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, index=True)
    color: Optional[str] = None
    meta_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    idempotency_key: Optional[str] = Field(default=None, index=True, unique=False)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Memory(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    ttl_expires_at: Optional[datetime] = Field(default=None, index=True)
    updated_at: datetime = Field(default_factory=_utcnow, index=True)


class Recipe(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    ingredients_json: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PlanWeek(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    week_start: date
    week_end: date
    request_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    plan_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    macros_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    event_ids_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)


class ShoppingList(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    plan_id: Optional[str] = Field(default=None, foreign_key="planweek.id")
    recipe_ids: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    items_json: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    generated_at: datetime = Field(default_factory=_utcnow)


class Skill(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    cadence_per_week: int = Field(default=1, ge=0)
    session_length_min: int = Field(default=30, ge=0)
    category: str = Field(default="skill")
    metadata_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=_utcnow)


class SkillSession(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    skill_id: str = Field(foreign_key="skill.id")
    event_id: Optional[str] = Field(default=None, foreign_key="event.id")
    scheduled_start: datetime
    duration_min: int
    outcome: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    next_focus: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


class PantryItem(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str = Field(index=True)
    quantity: float = Field(default=0)
    unit: Optional[str] = None
    category: Optional[str] = None
    opened_at: Optional[date] = None
    use_by: Optional[date] = Field(default=None, index=True)
    best_before: Optional[date] = None
    notes: Optional[str] = None
    updated_at: datetime = Field(default_factory=_utcnow, index=True)
