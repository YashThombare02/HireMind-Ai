"""Pure parsing logic for job descriptions — mirrors resume_parser.py's
"no DB, unit-testable" shape. See docs/ARCHITECTURE.md Module 7.
"""

import re
from dataclasses import dataclass, field

from app.services.skills_dictionary import extract_skills

_TITLE_RE = re.compile(r"Job Title:\s*(.+)", re.IGNORECASE)
_EXPERIENCE_RE = re.compile(r"Experience Required:\s*(.+)", re.IGNORECASE)


def _extract_bulleted_section(text: str, heading: str) -> list[str]:
    pattern = re.compile(rf"{re.escape(heading)}:?\s*\n((?:\s*-.*\n?)+)", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return []
    return [line.strip().lstrip("-").strip() for line in match.group(1).splitlines() if line.strip()]


@dataclass
class ParsedJobDescription:
    raw_text: str
    title: str = ""
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    experience_required: str | None = None
    responsibilities: list[str] = field(default_factory=list)


def parse_job_description(raw_text: str) -> ParsedJobDescription:
    text = raw_text.strip()

    title_match = _TITLE_RE.search(text)
    title = title_match.group(1).strip() if title_match else ""

    experience_match = _EXPERIENCE_RE.search(text)
    experience_required = experience_match.group(1).strip() if experience_match else None

    required_lines = _extract_bulleted_section(text, "Required Skills")
    preferred_lines = _extract_bulleted_section(text, "Preferred Skills")
    responsibilities = _extract_bulleted_section(text, "Responsibilities")

    # Each bullet ("FastAPI or Django") is matched against the skill
    # dictionary rather than kept verbatim, so "FastAPI or Django" yields
    # both ["fastapi", "django"] — consistent, dictionary-normalized skill
    # names on both the resume and JD side is what makes set-overlap
    # matching in matcher.py work at all.
    required_skills = sorted({s for line in required_lines for s in extract_skills(line)})
    preferred_skills = sorted({s for line in preferred_lines for s in extract_skills(line)})

    return ParsedJobDescription(
        raw_text=text,
        title=title,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        experience_required=experience_required,
        responsibilities=responsibilities,
    )
