"""LLM-based resume structuring — the primary parsing path.

Regex/keyword heuristics (resume_parser.py) can only ever cover the resume
templates someone has actually seen and coded for; a real resume with a
different-but-common layout broke that parser badly (see git history and
resume_parser.py's module docstring). Open-ended "understand this arbitrary
document's structure" is exactly the kind of problem an LLM generalizes
across templates far better than hand-written rules ever will.

This module is the primary path; resume_service.py falls back to
resume_parser.py's regex parser when this raises LLMUnavailableError (no
API key configured yet, or the LLM never returned usable JSON) — resume
upload should never hard-fail just because the LLM step didn't work.
"""

import logging

from pydantic import BaseModel, ValidationError

from app.prompts.resume_extraction_prompts import build_resume_extraction_prompt
from app.services.llm_client import LLMUnavailableError, generate_json
from app.services.resume_parser import ParsedResume
from app.services.skills_dictionary import extract_skills

logger = logging.getLogger("hireminds.resume_ai_parser")


class _Entry(BaseModel):
    title: str
    details: str = ""


class _LLMResumeExtraction(BaseModel):
    skills: list[str] = []
    education: list[_Entry] = []
    experience: list[_Entry] = []
    projects: list[_Entry] = []
    certifications: list[str] = []


async def extract_resume_with_llm(cleaned_text: str) -> ParsedResume:
    """Raises LLMUnavailableError — callers are expected to fall back to
    resume_parser.parse_resume_text(cleaned_text) when this happens.
    """
    prompt = build_resume_extraction_prompt(cleaned_text)
    raw = await generate_json(prompt, max_retries=1)

    try:
        extraction = _LLMResumeExtraction.model_validate(raw)
    except ValidationError as exc:
        # Valid JSON, wrong shape — same fallback path as "not JSON at all".
        raise LLMUnavailableError(f"LLM JSON didn't match the expected schema: {exc}") from exc

    # Union with the free, deterministic dictionary matcher rather than
    # trusting the LLM's skill list alone — catches known skill names the
    # LLM might phrase differently or skip, at zero extra cost or latency.
    dictionary_skills = set(extract_skills(cleaned_text))
    llm_skills = {s.strip().lower() for s in extraction.skills if s.strip()}
    all_skills = sorted(dictionary_skills | llm_skills)

    return ParsedResume(
        raw_text=cleaned_text,
        skills=all_skills,
        education=[e.model_dump() for e in extraction.education],
        experience=[e.model_dump() for e in extraction.experience],
        projects=[e.model_dump() for e in extraction.projects],
        certifications=[c for c in extraction.certifications if c.strip()],
    )
