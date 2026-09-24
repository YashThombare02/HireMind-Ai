import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import current_active_user
from app.db.models import Resume, User
from app.db.session import get_async_session
from app.services.ownership import get_owned_or_404
from app.services.resume_service import save_uploaded_resume

router = APIRouter(prefix="/resumes", tags=["resumes"])


class ResumeRead(BaseModel):
    id: uuid.UUID
    skills: list[str]
    education: list[dict]
    experience: list[dict]
    projects: list[dict]
    certifications: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeUpdate(BaseModel):
    skills: list[str] | None = None
    education: list[dict] | None = None
    experience: list[dict] | None = None
    projects: list[dict] | None = None
    certifications: list[str] | None = None


@router.post("/upload", response_model=ResumeRead, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await save_uploaded_resume(session, user.id, file)


@router.get("/{resume_id}", response_model=ResumeRead)
async def get_resume(
    resume_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await get_owned_or_404(session, Resume, resume_id, user.id)


@router.patch("/{resume_id}", response_model=ResumeRead)
async def update_resume(
    resume_id: uuid.UUID,
    payload: ResumeUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    resume = await get_owned_or_404(session, Resume, resume_id, user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(resume, field, value)
    await session.commit()
    await session.refresh(resume)
    return resume


@router.get("/{resume_id}/file")
async def download_resume_file(
    resume_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    resume = await get_owned_or_404(session, Resume, resume_id, user.id)
    # file_path is stored relative to the backend working directory —
    # resolved here, never exposed directly in the JSON response (ResumeRead
    # deliberately has no file_path field) so a client can't guess/probe
    # filesystem paths.
    absolute_path = os.path.join(os.getcwd(), resume.file_path)
    if not os.path.isfile(absolute_path):
        raise HTTPException(status_code=404, detail="Resume file not found.")
    return FileResponse(absolute_path, media_type="application/pdf", filename="resume.pdf")
