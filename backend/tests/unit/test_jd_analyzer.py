import json
import os

import pytest

from app.services.jd_analyzer import parse_job_description

SAMPLE_DATA_DIR = os.path.join(os.getcwd(), "sample_data")


def _load_ground_truth() -> dict:
    with open(os.path.join(SAMPLE_DATA_DIR, "ground_truth.json"), encoding="utf-8") as f:
        return json.load(f)


def _load_jd_text(stem: str) -> str:
    with open(os.path.join(SAMPLE_DATA_DIR, "job_descriptions", f"{stem}.txt"), encoding="utf-8") as f:
        return f.read()


GROUND_TRUTH = _load_ground_truth()


@pytest.mark.parametrize("stem", list(GROUND_TRUTH["job_descriptions"].keys()))
def test_required_and_preferred_skills_match_ground_truth(stem: str):
    expected = GROUND_TRUTH["job_descriptions"][stem]
    parsed = parse_job_description(_load_jd_text(stem))

    missing_required = set(expected["required_skills"]) - set(parsed.required_skills)
    missing_preferred = set(expected["preferred_skills"]) - set(parsed.preferred_skills)
    assert not missing_required, f"{stem}: missed required skills {missing_required}"
    assert not missing_preferred, f"{stem}: missed preferred skills {missing_preferred}"


def test_title_and_experience_extracted():
    parsed = parse_job_description(_load_jd_text("01_backend_developer_python"))
    assert parsed.title == "Backend Developer (Python)"
    assert parsed.experience_required == "0-2 years"


def test_responsibilities_extracted_as_list():
    parsed = parse_job_description(_load_jd_text("01_backend_developer_python"))
    assert len(parsed.responsibilities) >= 4
    assert any("REST APIs" in r for r in parsed.responsibilities)
