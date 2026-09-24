"""Pure parsing logic — no DB, no network — so it's unit-testable in
isolation. See app/services/resume_service.py for the DB-persistence
orchestration that wraps this. Design/edge cases per docs/ARCHITECTURE.md
Module 6.
"""

import re
from dataclasses import dataclass, field
from io import BytesIO

import fitz  # PyMuPDF

from app.services.skills_dictionary import extract_skills

MIN_EXTRACTED_TEXT_LENGTH = 50

SECTION_HEADERS = {"education", "skills", "experience", "projects", "certifications"}

_EDU_LINE_RE = re.compile(
    r"^(?P<degree>.+?)\s+in\s+(?P<field>.+?),\s*(?P<institution>.+?)\s*[—-]\s*"
    r"(?P<years>\d{4}\s*[-–]\s*\d{4})\s*$"
)


class InvalidPdfError(ValueError):
    """Raised when the uploaded bytes aren't a PDF PyMuPDF can open."""


class ScannedPdfError(ValueError):
    """Raised when a PDF opens fine but yields near-empty text (image-only)."""


@dataclass
class ParsedResume:
    raw_text: str
    skills: list[str] = field(default_factory=list)
    education: list[dict] = field(default_factory=list)
    experience: list[dict] = field(default_factory=list)
    projects: list[dict] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)


def extract_text_from_pdf(content: bytes) -> str:
    try:
        doc = fitz.open(stream=BytesIO(content), filetype="pdf")
    except Exception as exc:
        raise InvalidPdfError("File is not a valid PDF.") from exc

    try:
        text = "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()
    return text


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse runs of blank lines to exactly one, and trailing whitespace
    # per line, without collapsing the single blank lines that separate
    # entries within a section (section-entry splitting depends on them).
    lines = [line.rstrip() for line in text.split("\n")]
    cleaned: list[str] = []
    blank_run = 0
    for line in lines:
        if line.strip() == "":
            blank_run += 1
            if blank_run <= 1:
                cleaned.append("")
        else:
            blank_run = 0
            cleaned.append(line)
    return "\n".join(cleaned).strip()


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_key: str | None = None
    for line in text.split("\n"):
        stripped = line.strip()
        key = stripped.lower().rstrip(":")
        if key in SECTION_HEADERS and len(stripped) < 40:
            current_key = key
            sections[current_key] = []
            continue
        if current_key:
            sections[current_key].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def _split_lines(section_text: str) -> list[str]:
    return [line.strip() for line in section_text.splitlines() if line.strip()]


def _split_into_entries(section_text: str) -> list[dict]:
    """Blank-line-separated paragraphs become {"title": first line,
    "details": remaining lines joined}. A documented simplification — real
    resumes vary in format far more than this heuristic captures, but it
    handles the common "title line + bullet lines, blank line between
    entries" pattern used across sample_data/ and most resume templates.
    """
    entries = []
    for block in re.split(r"\n\s*\n", section_text.strip()):
        lines = _split_lines(block)
        if not lines:
            continue
        entries.append({"title": lines[0], "details": " ".join(lines[1:])})
    return entries


def _parse_education(section_text: str) -> list[dict]:
    entries: list[dict] = []
    current: dict | None = None
    for line in _split_lines(section_text):
        match = _EDU_LINE_RE.match(line)
        if match:
            current = {
                "degree": match.group("degree").strip(),
                "field": match.group("field").strip(),
                "institution": match.group("institution").strip(),
                "years": match.group("years").replace(" ", ""),
                "notes": "",
            }
            entries.append(current)
        elif current is not None:
            current["notes"] = (current["notes"] + " " + line).strip()
        else:
            # Doesn't match the expected pattern — keep the raw line rather
            # than silently dropping it or guessing wrong.
            entries.append({"raw": line})
    return entries


def parse_resume_text(raw_text: str) -> ParsedResume:
    cleaned = clean_text(raw_text)
    sections = split_sections(cleaned)

    return ParsedResume(
        raw_text=cleaned,
        skills=extract_skills(cleaned),
        education=_parse_education(sections.get("education", "")),
        experience=_split_into_entries(sections.get("experience", "")),
        projects=_split_into_entries(sections.get("projects", "")),
        certifications=_split_lines(sections.get("certifications", "")),
    )


def parse_resume_pdf(content: bytes) -> ParsedResume:
    text = extract_text_from_pdf(content)
    if len(text.strip()) < MIN_EXTRACTED_TEXT_LENGTH:
        raise ScannedPdfError(
            "This looks like a scanned/image-only PDF — please upload a text-based PDF."
        )
    return parse_resume_text(text)
