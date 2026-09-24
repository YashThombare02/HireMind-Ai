import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user
from app.db.models import AtsResult, JobDescription, Resume, User
from app.db.session import get_async_session
from app.services.matcher import compute_ats_score
from app.services.ownership import get_owned_or_404

router = APIRouter(prefix="/ats", tags=["ats"])


class ScoreRequest(BaseModel):
    resume_id: uuid.UUID
    jd_id: uuid.UUID
    force_recompute: bool = False


class AtsResultRead(BaseModel):
    id: uuid.UUID
    resume_id: uuid.UUID
    jd_id: uuid.UUID
    match_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    experience_relevance: float | None
    recommendation: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/score", response_model=AtsResultRead)
async def score(
    payload: ScoreRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    resume = await get_owned_or_404(session, Resume, payload.resume_id, user.id)
    jd = await get_owned_or_404(session, JobDescription, payload.jd_id, user.id)

    if not payload.force_recompute:
        existing_stmt = select(AtsResult).where(
            AtsResult.resume_id == resume.id, AtsResult.jd_id == jd.id
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

    result = await compute_ats_score(session, resume, jd)
    ats_result = AtsResult(resume_id=resume.id, jd_id=jd.id, **result)
    session.add(ats_result)
    await session.commit()
    await session.refresh(ats_result)
    return ats_result


@router.get("/{ats_result_id}", response_model=AtsResultRead)
async def get_ats_result(
    ats_result_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    # ats_results has no owner_id of its own — ownership is transitive via
    # its resume. Joined so the ownership check still happens in the query,
    # not fetch-then-check in Python.
    stmt = (
        select(AtsResult)
        .join(Resume, Resume.id == AtsResult.resume_id)
        .where(AtsResult.id == ats_result_id, Resume.user_id == user.id)
    )
    ats_result = (await session.execute(stmt)).scalar_one_or_none()
    if ats_result is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return ats_result
