"""DB-persistence orchestration around the pure resume_parser logic: file
storage, embedding, ownership caps. Kept separate from resume_parser.py so
the parsing logic stays unit-testable without a database.
"""

import logging
import os
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Resume
from app.services.embeddings import embed
from app.services.llm_client import LLMUnavailableError
from app.services.resume_ai_parser import extract_resume_with_llm
from app.services.resume_parser import (
    MIN_EXTRACTED_TEXT_LENGTH,
    InvalidPdfError,
    ParsedResume,
    clean_text,
    extract_text_from_pdf,
    parse_resume_text,
)

logger = logging.getLogger("hireminds.resume_service")

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
        raw_text = extract_text_from_pdf(content)
    except InvalidPdfError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if len(raw_text.strip()) < MIN_EXTRACTED_TEXT_LENGTH:
        raise HTTPException(
            status_code=422,
            detail="This looks like a scanned/image-only PDF — please upload a text-based PDF.",
        )
    cleaned_text = clean_text(raw_text)

    parsed: ParsedResume
    try:
        parsed = await extract_resume_with_llm(cleaned_text)
        logger.info("resume_parsed", extra={"user_id": str(user_id), "method": "llm"})
    except LLMUnavailableError as exc:
        # No API key configured yet, or the LLM never returned usable JSON —
        # fall back to the regex parser rather than failing the upload.
        logger.info(
            "resume_parsed", extra={"user_id": str(user_id), "method": "regex_fallback", "reason": str(exc)}
        )
        parsed = parse_resume_text(cleaned_text)

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
