"""DB-persistence orchestration around the pure resume_parser logic: file
storage, embedding, ownership caps. Kept separate from resume_parser.py so
the parsing logic stays unit-testable without a database.
"""

import os
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Resume
from app.services.embeddings import embed
from app.services.resume_parser import InvalidPdfError, ScannedPdfError, parse_resume_pdf

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "resumes")


async def _enforce_resume_cap(session: AsyncSession, user_id: uuid.UUID) -> None:
    count = await session.scalar(select(func.count()).select_from(Resume).where(Resume.user_id == user_id))
    if count is not None and count >= settings.max_resumes_per_user:
        raise HTTPException(
            status_code=400,
            detail=f"You've reached the maximum of {settings.max_resumes_per_user} uploaded resumes.",
        )


async def save_uploaded_resume(session: AsyncSession, user_id: uuid.UUID, file: UploadFile) -> Resume:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF.")

    content = await file.read()
    max_bytes = settings.max_resume_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400, detail=f"File exceeds the {settings.max_resume_size_mb}MB size limit."
        )

    await _enforce_resume_cap(session, user_id)

    try:
        parsed = parse_resume_pdf(content)
    except InvalidPdfError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScannedPdfError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Never trust the client-supplied filename for the on-disk path — avoids
    # path traversal and filename collisions.
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    stored_filename = f"{uuid.uuid4()}.pdf"
    stored_path = os.path.join(UPLOAD_DIR, stored_filename)
    with open(stored_path, "wb") as f:
        f.write(content)

    resume = Resume(
        user_id=user_id,
        file_path=os.path.join("uploads", "resumes", stored_filename),
        raw_text=parsed.raw_text,
        skills=parsed.skills,
        education=parsed.education,
        experience=parsed.experience,
        projects=parsed.projects,
        certifications=parsed.certifications,
        embedding=embed(parsed.raw_text),
    )
    session.add(resume)
    await session.commit()
    await session.refresh(resume)
    return resume
