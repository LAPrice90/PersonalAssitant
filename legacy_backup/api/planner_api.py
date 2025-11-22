from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .database import get_session
from .models import Event, Memory, PlanWeek

router = APIRouter()
TZ_UTC = timezone.utc


DEFAULT_MEAL_WINDOWS = {
    "breakfast": {"hour": 7, "minute": 30, "duration_min": 45},
    "lunch": {"hour": 12, "minute": 0, "duration_min": 60},
    "dinner": {"hour": 18, "minute": 30, "duration_min": 75},
}


class PlanGenerateRequest(BaseModel):
    week: str = Field(..., description="ISO week string, e.g. 2024-W10")
    people_per_meal: Dict[str, int] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)


class PlanGenerateResponse(BaseModel):
    plan_id: str
    macros: Dict[str, Any]


class PlanApplyRequest(BaseModel):
    plan_id: str
    tz_offset_minutes: int = Field(default=0, description="Offset from UTC in minutes")
    meal_windows: Dict[str, Dict[str, int]] = Field(
        default_factory=lambda: {k: dict(v) for k, v in DEFAULT_MEAL_WINDOWS.items()}
    )
    include_prep: bool = True
    include_travel: bool = True


class WindowsResponse(BaseModel):
    windows: List[Dict[str, Any]]


def _iso_week_to_date(week_str: str) -> date:
    try:
        year, week = week_str.split("-W")
        week_num = int(week)
        return datetime.strptime(f"{year} {week_num} 1", "%G %V %u").date()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(400, "Invalid ISO week format (use YYYY-Www)") from exc


def _default_plan(week_start: date) -> Dict[str, Any]:
    days: List[Dict[str, Any]] = []
    for offset in range(7):
        d = week_start + timedelta(days=offset)
        day_plan = {
            "date": d.isoformat(),
            "meals": [],
        }
        for meal_name in ("breakfast", "lunch", "dinner"):
            day_plan["meals"].append(
                {
                    "name": meal_name,
                    "recipe_id": None,
                    "notes": "Auto-generated placeholder",
                }
            )
        days.append(day_plan)
    return {"days": days}


def _estimate_macros(people_per_meal: Dict[str, int]) -> Dict[str, Any]:
    macros: Dict[str, Any] = {}
    default_macro = {"calories": 600, "protein_g": 30, "carbs_g": 70, "fat_g": 20}
    for meal, count in people_per_meal.items():
        macros[meal] = {
            "per_person": default_macro,
            "total": {k: v * max(count, 1) for k, v in default_macro.items()},
        }
    return macros or {"default": {"per_person": default_macro, "total": default_macro}}


@router.post("/plan.generate_week", response_model=PlanGenerateResponse)
def plan_generate_week(payload: PlanGenerateRequest, session: Session = Depends(get_session)):
    week_start = _iso_week_to_date(payload.week)
    plan = PlanWeek(
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        request_json=payload.model_dump(),
        plan_json=_default_plan(week_start),
        macros_json=_estimate_macros(payload.people_per_meal),
        event_ids_json={},
    )
    session.add(plan)
    session.commit()
    return PlanGenerateResponse(plan_id=plan.id, macros=plan.macros_json)


def _build_event_time(day: date, meal_name: str, window_cfg: Dict[str, Dict[str, int]], tz_offset: int) -> (datetime, datetime):
    cfg = window_cfg.get(meal_name, DEFAULT_MEAL_WINDOWS.get(meal_name, DEFAULT_MEAL_WINDOWS["dinner"]))
    start_local = datetime.combine(day, time(hour=cfg.get("hour", 18), minute=cfg.get("minute", 0)))
    duration = timedelta(minutes=cfg.get("duration_min", 60))
    tz = timezone(timedelta(minutes=tz_offset))
    start_dt = start_local.replace(tzinfo=tz).astimezone(TZ_UTC)
    end_dt = (start_local + duration).replace(tzinfo=tz).astimezone(TZ_UTC)
    return start_dt, end_dt


@router.post("/plan.apply_to_calendar")
def plan_apply_to_calendar(payload: PlanApplyRequest, session: Session = Depends(get_session)):
    plan = session.get(PlanWeek, payload.plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    plan_data = plan.plan_json or {}
    days = plan_data.get("days", [])
    tz_offset = payload.tz_offset_minutes
    window_cfg = payload.meal_windows or DEFAULT_MEAL_WINDOWS

    event_refs: Dict[str, List[str]] = plan.event_ids_json or {}

    for day_entry in days:
        day_date = date.fromisoformat(day_entry["date"])
        meal_events: List[str] = []
        for meal in day_entry.get("meals", []):
            meal_name = meal.get("name", "meal")
            title = f"{meal_name.title()}"
            start_dt, end_dt = _build_event_time(day_date, meal_name, window_cfg, tz_offset)
            meal_event = Event(
                title=title,
                start=start_dt,
                end=end_dt,
                category="meal",
                color="#7FB069",
                description=meal.get("notes"),
                meta_json={"meal": meal},
            )
            session.add(meal_event)
            session.commit()
            meal_events.append(meal_event.id)

            if payload.include_prep:
                prep_start = start_dt - timedelta(minutes=45)
                prep_end = start_dt - timedelta(minutes=15)
                prep_event = Event(
                    title=f"Prep: {title}",
                    start=prep_start,
                    end=prep_end,
                    category="prep",
                    color="#B5D99C",
                    meta_json={"meal": meal},
                )
                session.add(prep_event)
                session.commit()
                meal_events.append(prep_event.id)

            if payload.include_travel:
                travel_start = start_dt - timedelta(minutes=15)
                travel_end = start_dt
                travel_event = Event(
                    title=f"Travel: {title}",
                    start=travel_start,
                    end=travel_end,
                    category="travel",
                    color="#7AA5D2",
                    meta_json={"meal": meal},
                )
                session.add(travel_event)
                session.commit()
                meal_events.append(travel_event.id)
        if meal_events:
            event_refs[day_entry["date"]] = meal_events

    plan.event_ids_json = event_refs
    session.add(plan)
    session.commit()
    return {"plan_id": plan.id, "event_ids": event_refs}


@router.get("/windows.active", response_model=WindowsResponse)
def windows_active(date: date, session: Session = Depends(get_session)):
    key = f"windows:{date.isoformat()}"
    record = session.get(Memory, key)
    if not record:
        prefix = f"windows:{date.strftime('%A').lower()}"
        record = session.exec(select(Memory).where(Memory.key == prefix)).first()
    if not record:
        return WindowsResponse(windows=[])
    value = record.value_json or {}
    return WindowsResponse(windows=value.get("windows", []))
