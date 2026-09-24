import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user
from app.db.models import JobDescription, User
from app.db.session import get_async_session
from app.services.jd_service import create_job_description
from app.services.ownership import get_owned_or_404

router = APIRouter(prefix="/job-descriptions", tags=["job-descriptions"])


class CreateJobDescriptionRequest(BaseModel):
    raw_text: str = Field(min_length=1)


class JobDescriptionRead(BaseModel):
    id: uuid.UUID
    title: str
    required_skills: list[str]
    preferred_skills: list[str]
    experience_required: str | None
    responsibilities: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class JobDescriptionUpdate(BaseModel):
    title: str | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    experience_required: str | None = None
    responsibilities: list[str] | None = None


@router.post("", response_model=JobDescriptionRead, status_code=201)
async def submit_job_description(
    payload: CreateJobDescriptionRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await create_job_description(session, user.id, payload.raw_text)


@router.get("/{jd_id}", response_model=JobDescriptionRead)
async def get_job_description(
    jd_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await get_owned_or_404(session, JobDescription, jd_id, user.id)


@router.patch("/{jd_id}", response_model=JobDescriptionRead)
async def update_job_description(
    jd_id: uuid.UUID,
    payload: JobDescriptionUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    jd = await get_owned_or_404(session, JobDescription, jd_id, user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(jd, field, value)
    await session.commit()
    await session.refresh(jd)
    return jd
