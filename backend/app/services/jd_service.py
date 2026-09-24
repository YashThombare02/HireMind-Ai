import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import JobDescription
from app.services.embeddings import embed
from app.services.jd_analyzer import parse_job_description


def _validate_length(raw_text: str) -> None:
    length = len(raw_text.strip())
    if length < settings.min_jd_text_length:
        raise HTTPException(
            status_code=422,
            detail=f"Job description is too short (minimum {settings.min_jd_text_length} characters).",
        )
    if length > settings.max_jd_text_length:
        raise HTTPException(
            status_code=422,
            detail=f"Job description is too long (maximum {settings.max_jd_text_length} characters).",
        )


async def create_job_description(session: AsyncSession, user_id: uuid.UUID, raw_text: str) -> JobDescription:
    _validate_length(raw_text)
    parsed = parse_job_description(raw_text)

    jd = JobDescription(
        user_id=user_id,
        title=parsed.title or "Untitled role",
        raw_text=parsed.raw_text,
        required_skills=parsed.required_skills,
        preferred_skills=parsed.preferred_skills,
        experience_required=parsed.experience_required,
        responsibilities=parsed.responsibilities,
        embedding=embed(parsed.raw_text),
    )
    session.add(jd)
    await session.commit()
    await session.refresh(jd)
    return jd
