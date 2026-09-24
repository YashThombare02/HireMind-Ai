import json
import os

import pytest

from app.services.resume_parser import (
    ScannedPdfError,
    clean_text,
    parse_resume_pdf,
    parse_resume_text,
    split_sections,
)

SAMPLE_DATA_DIR = os.path.join(os.getcwd(), "sample_data")
GROUND_TRUTH_PATH = os.path.join(SAMPLE_DATA_DIR, "ground_truth.json")


def _load_ground_truth() -> dict:
    with open(GROUND_TRUTH_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_resume_text(stem: str) -> str:
    path = os.path.join(SAMPLE_DATA_DIR, "resumes", f"{stem}.txt")
    with open(path, encoding="utf-8") as f:
        return f.read()


GROUND_TRUTH = _load_ground_truth()


def test_split_sections_finds_all_headers():
    text = _load_resume_text("01_priya_sharma_backend_dev")
    sections = split_sections(clean_text(text))
    assert set(sections.keys()) == {"education", "skills", "experience", "projects", "certifications"}
    assert "FastAPI" in sections["skills"]


@pytest.mark.parametrize("stem", list(GROUND_TRUTH["resumes"].keys()))
def test_skill_extraction_matches_ground_truth(stem: str):
    expected = GROUND_TRUTH["resumes"][stem]
    text = _load_resume_text(stem)
    parsed = parse_resume_text(text)

    expected_skills = set(expected["expected_skills"])
    extracted_skills = set(parsed.skills)

    # At least the expected genuinely-backed skills must be found — the
    # inflated resume additionally lists skills in its SKILLS line that
    # extraction will also pick up (that's correct: extraction just reads
    # what's written; distinguishing "claimed" from "verified" is Module 12's
    # job in Phase 5, not this parser's).
    missing = expected_skills - extracted_skills
    assert not missing, f"{stem}: parser missed expected skills {missing}"


def test_education_parsing_extracts_degree_institution_years():
    text = _load_resume_text("01_priya_sharma_backend_dev")
    parsed = parse_resume_text(text)
    assert len(parsed.education) >= 1
    entry = parsed.education[0]
    assert entry.get("degree", "").startswith("B.Tech")
    assert "Pune Institute of Technology" in entry.get("institution", "")
    assert entry.get("years") == "2022-2026"


def test_certifications_parsed_as_separate_lines():
    text = _load_resume_text("01_priya_sharma_backend_dev")
    parsed = parse_resume_text(text)
    assert len(parsed.certifications) == 2


def test_experience_and_projects_split_into_entries():
    text = _load_resume_text("01_priya_sharma_backend_dev")
    parsed = parse_resume_text(text)
    assert len(parsed.experience) == 2
    assert len(parsed.projects) == 2
    assert "CloudLedger Technologies" in parsed.experience[0]["title"]


def test_parse_resume_pdf_rejects_near_empty_text():
    import fitz

    doc = fitz.open()
    doc.new_page()  # blank page, no text
    pdf_bytes = doc.tobytes()
    doc.close()

    with pytest.raises(ScannedPdfError):
        parse_resume_pdf(pdf_bytes)
