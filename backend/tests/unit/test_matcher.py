from app.services.matcher import (
    compute_education_match,
    compute_experience_match,
    compute_project_relevance,
    compute_skill_match,
)


def test_skill_match_uses_required_skills_when_present():
    score = compute_skill_match(
        resume_skills={"python", "fastapi", "docker"},
        required_skills={"python", "fastapi", "sql"},
        preferred_skills={"docker"},
    )
    assert score == 2 / 3


def test_skill_match_falls_back_to_preferred_when_no_required():
    score = compute_skill_match(
        resume_skills={"docker", "redis"},
        required_skills=set(),
        preferred_skills={"docker", "redis", "kubernetes"},
    )
    assert score == 2 / 3


def test_skill_match_is_zero_when_neither_list_has_anything():
    score = compute_skill_match(resume_skills={"python"}, required_skills=set(), preferred_skills=set())
    assert score == 0.0


def test_skill_match_is_capped_at_one():
    score = compute_skill_match(
        resume_skills={"python", "sql", "extra_skill_not_required"},
        required_skills={"python"},
        preferred_skills=set(),
    )
    assert score == 1.0


def test_experience_match_full_when_jd_has_no_requirement():
    assert compute_experience_match([], None) == 1.0


def test_experience_match_partial_when_no_experience_entries():
    assert compute_experience_match([], "0-2 years") == 0.3


def test_experience_match_full_when_at_least_one_entry():
    assert compute_experience_match([{"title": "Intern"}], "0-2 years") == 1.0


def test_education_match_full_for_btech():
    entries = [{"degree": "B.Tech", "field": "Computer Engineering", "institution": "X"}]
    assert compute_education_match(entries) == 1.0


def test_education_match_partial_for_unrecognized_degree():
    entries = [{"degree": "Diploma", "field": "X", "institution": "Y"}]
    assert compute_education_match(entries) == 0.5


def test_education_match_zero_when_no_education_at_all():
    assert compute_education_match([]) == 0.0


def test_project_relevance_counts_skill_mentions():
    projects = [{"title": "Resume Matcher", "details": "Built with Python and FastAPI"}]
    score = compute_project_relevance(projects, {"python", "fastapi", "docker"})
    assert score == 2 / 3


def test_project_relevance_zero_when_no_jd_skills():
    assert compute_project_relevance([{"title": "X", "details": "Y"}], set()) == 0.0
