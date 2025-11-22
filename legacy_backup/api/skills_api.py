from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .database import get_session
from .models import Event, Skill, SkillSession

router = APIRouter()
TZ_UTC = timezone.utc


class SkillUpsertRequest(BaseModel):
    id: Optional[str] = None
    name: str
    cadence_per_week: int = Field(default=1, ge=0)
    session_length_min: int = Field(default=30, ge=0)
    category: str = Field(default="skill")
    metadata: Dict[str, str] = Field(default_factory=dict)


class SkillResponse(BaseModel):
    id: str
    name: str
    cadence_per_week: int
    session_length_min: int
    category: str
    metadata: Dict[str, str]

    @classmethod
    def from_model(cls, skill: Skill) -> "SkillResponse":
        return cls(
            id=skill.id,
            name=skill.name,
            cadence_per_week=skill.cadence_per_week,
            session_length_min=skill.session_length_min,
            category=skill.category,
            metadata=skill.metadata_json or {},
        )


class ScheduleWeekRequest(BaseModel):
    week: str
    skill_ids: Optional[List[str]] = None
    tz_offset_minutes: int = 0
    start_hour: int = 9
    gap_minutes: int = 120


class ScheduleWeekResponse(BaseModel):
    scheduled_sessions: List[str]


class SkillLogRequest(BaseModel):
    session_id: str
    outcome: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    next_focus: Optional[str] = None


class BreakPolicyRequest(BaseModel):
    start_date: date
    end_date: date
    work_category: str = "work"
    break_category: str = "break"
    interval_minutes: int = Field(default=90, ge=15)
    break_length_minutes: int = Field(default=15, ge=5)


def _iso_week_start(week: str) -> date:
    try:
        year, week_num = week.split("-W")
        return datetime.strptime(f"{year} {int(week_num)} 1", "%G %V %u").date()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(400, "Invalid ISO week format") from exc


@router.post("/skills.upsert", response_model=SkillResponse)
def skills_upsert(payload: SkillUpsertRequest, session: Session = Depends(get_session)):
    if payload.id:
        skill = session.get(Skill, payload.id)
    else:
        skill = None
    if skill:
        skill.name = payload.name
        skill.cadence_per_week = payload.cadence_per_week
        skill.session_length_min = payload.session_length_min
        skill.category = payload.category
        skill.metadata_json = payload.metadata
        skill.updated_at = datetime.now(timezone.utc)
    else:
        skill = Skill(
            name=payload.name,
            cadence_per_week=payload.cadence_per_week,
            session_length_min=payload.session_length_min,
            category=payload.category,
            metadata_json=payload.metadata,
        )
        session.add(skill)
    session.commit()
    session.refresh(skill)
    return SkillResponse.from_model(skill)


def _schedule_slots(week_start: date, cadence: int, start_hour: int, gap_minutes: int) -> List[datetime]:
    slots: List[datetime] = []
    day_pointer = week_start
    current_time = time(hour=start_hour, minute=0)
    for _ in range(cadence):
        slot_datetime = datetime.combine(day_pointer, current_time)
        slots.append(slot_datetime)
        current_dt = slot_datetime + timedelta(minutes=gap_minutes)
        day_pointer = current_dt.date()
        current_time = current_dt.time()
        if current_time.hour >= 20:
            day_pointer += timedelta(days=1)
            current_time = time(hour=start_hour, minute=0)
    return slots


@router.post("/skills.schedule_week", response_model=ScheduleWeekResponse)
def skills_schedule_week(payload: ScheduleWeekRequest, session: Session = Depends(get_session)):
    week_start = _iso_week_start(payload.week)
    skills_query = select(Skill)
    if payload.skill_ids:
        skills_query = skills_query.where(Skill.id.in_(payload.skill_ids))
    skills = session.exec(skills_query).all()
    if not skills:
        raise HTTPException(404, "No skills found")

    tz = timezone(timedelta(minutes=payload.tz_offset_minutes))
    scheduled_ids: List[str] = []

    # Remove existing sessions for the week to avoid duplicates
    week_end = week_start + timedelta(days=7)
    existing_sessions = session.exec(
        select(SkillSession).where(
            SkillSession.scheduled_start >= datetime.combine(week_start, time.min, tzinfo=TZ_UTC),
            SkillSession.scheduled_start < datetime.combine(week_end, time.min, tzinfo=TZ_UTC),
        )
    ).all()
    for sess in existing_sessions:
        if sess.event_id:
            event = session.get(Event, sess.event_id)
            if event:
                session.delete(event)
        session.delete(sess)
    session.commit()

    for skill in skills:
        slots = _schedule_slots(week_start, skill.cadence_per_week, payload.start_hour, payload.gap_minutes)
        for slot in slots:
            start_local = slot.replace(tzinfo=tz)
            start_utc = start_local.astimezone(TZ_UTC)
            end_utc = start_utc + timedelta(minutes=skill.session_length_min)
            event = Event(
                title=f"Skill: {skill.name}",
                start=start_utc,
                end=end_utc,
                category=skill.category,
                color="#C44E52",
                meta_json={"skill_id": skill.id},
            )
            session.add(event)
            session.commit()
            skill_session = SkillSession(
                skill_id=skill.id,
                event_id=event.id,
                scheduled_start=start_utc,
                duration_min=skill.session_length_min,
                outcome=None,
                next_focus=None,
            )
            session.add(skill_session)
            session.commit()
            scheduled_ids.append(skill_session.id)
    return ScheduleWeekResponse(scheduled_sessions=scheduled_ids)


@router.post("/skills.log_session")
def skills_log_session(payload: SkillLogRequest, session: Session = Depends(get_session)):
    skill_session = session.get(SkillSession, payload.session_id)
    if not skill_session:
        raise HTTPException(404, "Session not found")
    skill_session.outcome = payload.outcome
    skill_session.rating = payload.rating
    skill_session.next_focus = payload.next_focus
    session.add(skill_session)
    session.commit()
    return {"status": "logged"}


@router.post("/breaks.apply_policy")
def breaks_apply_policy(payload: BreakPolicyRequest, session: Session = Depends(get_session)):
    start_dt = datetime.combine(payload.start_date, time.min).replace(tzinfo=TZ_UTC)
    end_dt = datetime.combine(payload.end_date + timedelta(days=1), time.min).replace(tzinfo=TZ_UTC)
    work_events = session.exec(
        select(Event).where(
            Event.category == payload.work_category,
            Event.start >= start_dt,
            Event.end <= end_dt,
        )
    ).all()

    # Remove existing breaks in window
    existing_breaks = session.exec(
        select(Event).where(
            Event.category == payload.break_category,
            Event.start >= start_dt,
            Event.end <= end_dt,
        )
    ).all()
    for ev in existing_breaks:
        session.delete(ev)
    session.commit()

    created: List[str] = []
    for work in work_events:
        cursor = work.start + timedelta(minutes=payload.interval_minutes)
        while cursor + timedelta(minutes=payload.break_length_minutes) < work.end:
            break_event = Event(
                title="Break",
                start=cursor,
                end=cursor + timedelta(minutes=payload.break_length_minutes),
                category=payload.break_category,
                color="#F2C14E",
                meta_json={"source": "break_policy", "work_event_id": work.id},
            )
            session.add(break_event)
            session.commit()
            created.append(break_event.id)
            cursor += timedelta(minutes=payload.interval_minutes)
    return {"created_breaks": created}
