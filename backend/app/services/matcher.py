"""Resume-JD matching and the ATS scoring formula. See docs/ARCHITECTURE.md
Module 8 — deliberately an explainable weighted formula, not an opaque AI
score, so it can be decomposed (needed for the Phase 6 bias audit) and so a
candidate's dashboard can explain *why* they got the score they did.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobDescription, Resume
from app.services.embeddings import embed

WEIGHTS = {
    "skill_match": 0.40,
    "experience_match": 0.25,
    "education_match": 0.15,
    "project_relevance": 0.10,
    "semantic_similarity": 0.10,
}


def compute_skill_match(
    resume_skills: set[str], required_skills: set[str], preferred_skills: set[str]
) -> float:
    if required_skills:
        return min(len(resume_skills & required_skills) / len(required_skills), 1.0)
    if preferred_skills:
        return min(len(resume_skills & preferred_skills) / len(preferred_skills), 1.0)
    # Neither list had anything extractable — division by zero avoided by
    # falling all the way through to 0 rather than guessing.
    return 0.0


def compute_experience_match(resume_experience: list, jd_experience_required: str | None) -> float:
    if not jd_experience_required:
        return 1.0
    # Simplification, documented: this checks *presence* of at least one
    # parsed experience entry rather than parsing exact years from date
    # ranges (which would need much more robust date parsing than is in
    # scope). Every sample_data JD targets entry-level candidates, where
    # "has at least one real internship" is a reasonable proxy signal.
    return 1.0 if resume_experience else 0.3


def compute_education_match(resume_education: list) -> float:
    if not resume_education:
        return 0.0
    degree_text = " ".join(
        f"{entry.get('degree', '')} {entry.get('raw', '')}" for entry in resume_education
    ).lower()
    if any(keyword in degree_text for keyword in ["b.tech", "b.e.", "b.e ", "bachelor"]):
        return 1.0
    return 0.5


def compute_project_relevance(resume_projects: list, jd_skills: set[str]) -> float:
    if not jd_skills:
        return 0.0
    project_text = " ".join(
        f"{p.get('title', '')} {p.get('details', '')}" for p in resume_projects
    ).lower()
    hits = sum(1 for skill in jd_skills if skill in project_text)
    return min(hits / len(jd_skills), 1.0)


async def compute_semantic_similarity(session: AsyncSession, resume_id: uuid.UUID, jd_id: uuid.UUID) -> float:
    query = text(
        """
        SELECT 1 - (r.embedding <=> j.embedding) AS similarity
        FROM resumes r, job_descriptions j
        WHERE r.id = :resume_id AND j.id = :jd_id
          AND r.embedding IS NOT NULL AND j.embedding IS NOT NULL
        """
    )
    result = await session.execute(query, {"resume_id": resume_id, "jd_id": jd_id})
    row = result.first()
    if row is None or row.similarity is None:
        return 0.0
    # Clamped: pgvector's <=> is cosine *distance* (0 identical..2 opposite);
    # 1-distance can technically go negative for very dissimilar text, which
    # isn't meaningful as a 0-1 "match" signal here.
    return max(0.0, min(1.0, float(row.similarity)))


async def ensure_embedding(session: AsyncSession, row: Resume | JobDescription) -> None:
    """Lazy backfill: computes and persists an embedding if one is missing
    (e.g. a row created before this code existed), instead of failing the
    score request.
    """
    if row.embedding is None:
        row.embedding = embed(row.raw_text)
        await session.flush()


def _recommendation(match_score: float, missing_skills: list[str], required: set[str], preferred: set[str]) -> str:
    if not required and not preferred:
        return "This job description had too few extractable requirements to score confidently."
    if match_score >= 70:
        return "Strong match — proceed to assessment."
    if match_score >= 40:
        shown = ", ".join(missing_skills[:5]) or "a few key skills"
        return f"Partial match — missing: {shown}."
    return "Limited match with this role's requirements."


async def compute_ats_score(session: AsyncSession, resume: Resume, jd: JobDescription) -> dict:
    await ensure_embedding(session, resume)
    await ensure_embedding(session, jd)

    resume_skills = set(resume.skills or [])
    required = set(jd.required_skills or [])
    preferred = set(jd.preferred_skills or [])

    matched = sorted(resume_skills & (required | preferred))
    missing = sorted(required - resume_skills)

    skill_match = compute_skill_match(resume_skills, required, preferred)
    experience_match = compute_experience_match(resume.experience or [], jd.experience_required)
    education_match = compute_education_match(resume.education or [])
    project_relevance = compute_project_relevance(resume.projects or [], required | preferred)
    semantic_similarity = await compute_semantic_similarity(session, resume.id, jd.id)

    match_score = 100 * (
        WEIGHTS["skill_match"] * skill_match
        + WEIGHTS["experience_match"] * experience_match
        + WEIGHTS["education_match"] * education_match
        + WEIGHTS["project_relevance"] * project_relevance
        + WEIGHTS["semantic_similarity"] * semantic_similarity
    )
    match_score = round(match_score, 1)

    return {
        "match_score": match_score,
        "matched_skills": matched,
        "missing_skills": missing,
        "experience_relevance": round(experience_match, 2),
        "recommendation": _recommendation(match_score, missing, required, preferred),
    }
