import json
import os

import pytest

from app.services.resume_parser import (
    ScannedPdfError,
    _parse_certifications,
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


def test_education_parsing_keeps_degree_and_institution_together():
    # v1 tried to split into {degree, institution, years} fields via a
    # single-line regex; that only ever matched sample_data/'s own format
    # and broke badly on a real resume with institution/degree/dates split
    # across separate lines (see resume_parser.py's module docstring). v2
    # trades precise field extraction for robustness: one entry per
    # institution, with everything else folded into "details".
    text = _load_resume_text("01_priya_sharma_backend_dev")
    parsed = parse_resume_text(text)
    assert len(parsed.education) >= 1
    entry = parsed.education[0]
    assert "B.Tech" in entry["title"]
    assert "Pune Institute of Technology" in entry["title"]
    assert "2022-2026" in entry["title"]


def test_education_parsing_splits_entries_with_dates_on_a_separate_line():
    # The real-world case that broke v1: institution name and its date
    # range on two separate lines instead of one, with degree/CGPA lines
    # following — a very common template shape sample_data/ didn't cover.
    text = (
        "EDUCATION\n"
        "Example Institute of Technology\n"
        "2023 - 2027\n"
        "Bachelor of Technology in Computer Science\n"
        "CGPA: 8.5\n"
        "Example Junior College\n"
        "2021 - 2023\n"
        "Higher Secondary Certificate\n"
        "Percentage: 80%\n"
        "SKILLS\n"
        "Python, SQL\n"
    )
    parsed = parse_resume_text(text)
    assert len(parsed.education) == 2
    assert "Example Institute of Technology" in parsed.education[0]["title"]
    assert "2023 - 2027" in parsed.education[0]["details"]
    assert "CGPA: 8.5" in parsed.education[0]["details"]
    assert "Example Junior College" in parsed.education[1]["title"]


def test_certifications_parsed_as_separate_lines():
    text = _load_resume_text("01_priya_sharma_backend_dev")
    parsed = parse_resume_text(text)
    assert len(parsed.certifications) == 2


def test_technical_skills_heading_is_recognized_as_skills_section():
    # Real bug: only the exact heading "Skills" was recognized, so "Technical
    # Skills" (a very common variant) wasn't — its content silently bled
    # into whatever section came before it in the document.
    text = (
        "EDUCATION\n"
        "Example University\n"
        "2022 - 2026\n"
        "TECHNICAL SKILLS\n"
        "Languages: Python, SQL\n"
        "EXPERIENCE\n"
        "Some Role\n"
        "Did things.\n"
    )
    sections = split_sections(clean_text(text))
    assert "Languages: Python, SQL" in sections["skills"]
    assert "Languages: Python, SQL" not in sections["education"]


def test_header_substring_match_does_not_false_positive_on_body_text():
    # Real bug: "Docker Essentials — IBM SkillsBuild" (a certification name)
    # contains "skills" as a substring and was mistaken for a new "Skills"
    # section heading, silently truncating the certifications section.
    text = (
        "CERTIFICATIONS\n"
        "Python for Everybody — University of Michigan (Coursera)\n"
        "Docker Essentials — IBM SkillsBuild\n"
    )
    sections = split_sections(clean_text(text))
    assert "skills" not in sections
    assert "Docker Essentials" in sections["certifications"]


def test_certifications_merge_multi_line_entries():
    # Real bug: a 3-line-per-certification listing (title / date /
    # instructor) produced 3 garbage fragments instead of 1 clean entry.
    text = (
        "CERTIFICATIONS\n"
        "Python Full Course For Beginners (Cursa)\n"
        "Jan 2025\n"
        "Instructor: Adrian Medeiros\n"
        "Complete Guide in HTML, CSS and JavaScript (Udemy)\n"
        "Jul 2024\n"
        "Instructor: Jerome Morales\n"
    )
    sections = split_sections(clean_text(text))
    certs = _parse_certifications(sections["certifications"])
    assert len(certs) == 2
    assert "Python Full Course For Beginners (Cursa)" in certs[0]
    assert "Adrian Medeiros" in certs[0]


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
