"""Pure parsing logic — no DB, no network — so it's unit-testable in
isolation. See app/services/resume_service.py for the DB-persistence
orchestration that wraps this. Design/edge cases per docs/ARCHITECTURE.md
Module 6.

v2 note: the original version of this file was written and tested only
against sample_data/'s own synthetic resumes, and broke badly on a real
resume with a different (very common) template — "Technical Skills" instead
of "Skills", institution/degree/dates split across separate lines instead of
one line, multi-line certification entries, and two project entries with no
blank line between them. This version replaces the single-line-regex/
blank-line-only heuristics with more general "continuation line" detection
that was verified against that real resume as well as sample_data/.
"""

import re
from dataclasses import dataclass, field
from io import BytesIO

import fitz  # PyMuPDF

from app.services.skills_dictionary import extract_skills

MIN_EXTRACTED_TEXT_LENGTH = 50

# Substring match, not exact — real resumes use "Technical Skills", "Work
# Experience", "Academic Projects", etc. Structural guards in
# _looks_like_header() do the real false-positive filtering (see there for
# why "certifications"/"certificates" — plural — rather than "certif": a
# resume's education section legitimately contains "...School Certificate"
# lines, singular, which must NOT be mistaken for the certifications
# heading).
SECTION_KEYWORDS = {
    "education": ["education"],
    "skills": ["skills"],
    "experience": ["experience"],
    "projects": ["projects"],
    "certifications": ["certifications", "certificates", "licenses"],
}
MAX_HEADER_LINE_LENGTH = 40
MAX_HEADER_WORDS = 5
# A real section heading is short and unpunctuated ("Technical Skills"). A
# body/bullet line that happens to contain a keyword as a substring
# ("Docker Essentials — IBM SkillsBuild", "Higher Secondary School
# Certificate") almost always has one of these, so their presence rules a
# line out even if short enough on word count alone.
_HEADER_DISQUALIFYING_RE = re.compile(r"[()@|•\d]|—| - |,")

_BULLET_PREFIXES = ("•", "-", "*", "◦", "‣")
_SENTENCE_END = (".", "!", "?", ":")

# A line that's *only* a year or year-range ("2023 - 2027", "(2022–2023)")
_YEAR_ONLY_RE = re.compile(r"^\(?\d{4}\s*[-–—to]{1,4}\s*\d{4}\)?\.?$", re.IGNORECASE)
# Degree lines commonly start with one of these regardless of everything else
_DEGREE_PREFIX_RE = re.compile(
    r"^(bachelor|master|ph\.?d|b\.?\s?tech|b\.?\s?e\.?|m\.?\s?tech|m\.?\s?e\.?|"
    r"diploma|higher secondary|secondary school|associate)",
    re.IGNORECASE,
)
# "CGPA: 8.02", "Percentage: 74.83%", "Grade: A" — a label-value line, never
# the start of a new education entry
_LABEL_LINE_RE = re.compile(r"^(cgpa|gpa|percentage|grade|marks)\s*[:\-]", re.IGNORECASE)
# "Instructor: X", "Issued by: X" — a detail line attached to the
# certification named on the previous line, not a new certification
_CERT_DETAIL_PREFIX_RE = re.compile(r"^(instructor|issued by|issuer|credential id)\s*[:\-]", re.IGNORECASE)
# A bare date line like "Jan 2025" or "June 2025" attached to a certification
_DATE_ONLY_RE = re.compile(
    r"^[A-Za-z]{3,9}\.?\s+\d{1,2},?\s*\d{4}$|^[A-Za-z]{3,9}\.?\s+\d{4}$", re.IGNORECASE
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
        # sort=True asks PyMuPDF to order text top-to-bottom then
        # left-to-right by position rather than raw content-stream order —
        # helps considerably on multi-column layouts (common in resumes)
        # where the raw order can otherwise interleave unrelated columns.
        text = "\n".join(page.get_text(sort=True) for page in doc)
    finally:
        doc.close()
    return text


_INTRA_LINE_WHITESPACE_RE = re.compile(r"[ \t]{2,}")


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse runs of blank lines to exactly one, and trailing whitespace
    # per line, without collapsing the single blank lines that separate
    # entries within a section (section-entry splitting depends on them).
    # Also collapse long internal whitespace runs — sort=True extraction
    # (see extract_text_from_pdf) merges same-row multi-column text onto one
    # line by joining them with a run of spaces reflecting their on-page
    # gap, which looks fine on screen but reads oddly as plain text.
    lines = [_INTRA_LINE_WHITESPACE_RE.sub("  ", line.rstrip()) for line in text.split("\n")]
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


def _looks_like_header(line: str) -> bool:
    if not line or len(line) >= MAX_HEADER_LINE_LENGTH:
        return False
    if _HEADER_DISQUALIFYING_RE.search(line):
        return False
    return len(line.split()) <= MAX_HEADER_WORDS


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_key: str | None = None
    for line in text.split("\n"):
        stripped = line.strip()
        matched_key = None
        if _looks_like_header(stripped):
            lowered = stripped.lower()
            for key, keywords in SECTION_KEYWORDS.items():
                if any(keyword in lowered for keyword in keywords):
                    matched_key = key
                    break
        if matched_key:
            current_key = matched_key
            sections.setdefault(current_key, [])
            continue
        if current_key:
            sections[current_key].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def _split_lines(section_text: str) -> list[str]:
    return [line.strip() for line in section_text.splitlines() if line.strip()]


def _finalize_entry(lines: list[str]) -> dict:
    return {"title": lines[0], "details": " ".join(lines[1:]).strip()}


def _split_block_into_entries(block_lines: list[str]) -> list[list[str]]:
    """Within one blank-line-delimited block, further split at the point
    where a non-bullet "title" line follows a *completed* bullet — handles
    resumes that pack multiple entries (e.g. two projects) into one section
    with no blank line between them, which is common because a PDF's visual
    gap doesn't always survive text extraction as a literal blank line.

    A wrapped bullet ("• Did something long that wraps onto...\\nthe next
    line.") is told apart from a genuine new entry by whether the previous
    line ends with sentence-ending punctuation: a wrap cuts off mid-sentence
    (no trailing period), a finished bullet doesn't.
    """
    sub_entries: list[list[str]] = [[]]
    seen_bullet = False
    for line in block_lines:
        is_bullet = line.startswith(_BULLET_PREFIXES)
        current = sub_entries[-1]
        if is_bullet:
            seen_bullet = True
            current.append(line)
            continue

        prev_ends_sentence = bool(current) and current[-1].rstrip().endswith(_SENTENCE_END)
        if seen_bullet and prev_ends_sentence:
            # Previous bullet finished cleanly — this non-bullet line is the
            # start of a new entry.
            sub_entries.append([line])
            seen_bullet = False
        elif seen_bullet and not prev_ends_sentence:
            # Previous bullet was cut off mid-sentence — this line is its
            # wrapped continuation, not a new entry.
            current[-1] = f"{current[-1]} {line}"
        else:
            current.append(line)
    return [entry for entry in sub_entries if entry]


def _split_into_entries(section_text: str) -> list[dict]:
    entries: list[dict] = []
    for block in re.split(r"\n\s*\n", section_text.strip()):
        lines = _split_lines(block)
        if not lines:
            continue
        for sub_lines in _split_block_into_entries(lines):
            entries.append(_finalize_entry(sub_lines))
    return entries


def _is_education_continuation(line: str) -> bool:
    return bool(_YEAR_ONLY_RE.match(line) or _DEGREE_PREFIX_RE.match(line) or _LABEL_LINE_RE.match(line))


def _parse_education(section_text: str) -> list[dict]:
    """A new entry starts at any line that isn't a recognized "continuation"
    (a bare year/year-range, a degree-name line, or a CGPA/percentage/grade
    label line) — so institution/degree/dates can be split across as many
    lines as a given template uses, instead of requiring one exact format.
    """
    entries: list[dict] = []
    for line in _split_lines(section_text):
        if entries and _is_education_continuation(line):
            entries[-1]["details"] = f"{entries[-1]['details']} {line}".strip()
        else:
            entries.append({"title": line, "details": ""})
    return entries


def _parse_certifications(section_text: str) -> list[str]:
    """A new certification starts at any line that isn't a recognized
    "detail" line (an "Instructor:"/"Issued by:" line, or a bare date) —
    mirrors _parse_education's approach for the same reason: real
    certification listings are often 2-3 lines per entry, not one.
    """
    certs: list[str] = []
    for line in _split_lines(section_text):
        is_detail = bool(_CERT_DETAIL_PREFIX_RE.match(line) or _DATE_ONLY_RE.match(line))
        if certs and is_detail:
            certs[-1] = f"{certs[-1]} ({line})"
        else:
            certs.append(line)
    return certs


def parse_resume_text(raw_text: str) -> ParsedResume:
    cleaned = clean_text(raw_text)
    sections = split_sections(cleaned)

    return ParsedResume(
        raw_text=cleaned,
        skills=extract_skills(cleaned),
        education=_parse_education(sections.get("education", "")),
        experience=_split_into_entries(sections.get("experience", "")),
        projects=_split_into_entries(sections.get("projects", "")),
        certifications=_parse_certifications(sections.get("certifications", "")),
    )


def parse_resume_pdf(content: bytes) -> ParsedResume:
    text = extract_text_from_pdf(content)
    if len(text.strip()) < MIN_EXTRACTED_TEXT_LENGTH:
        raise ScannedPdfError(
            "This looks like a scanned/image-only PDF — please upload a text-based PDF."
        )
    return parse_resume_text(text)
