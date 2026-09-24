import pytest

from app.services.llm_client import LLMUnavailableError
from app.services.resume_ai_parser import extract_resume_with_llm

SAMPLE_LLM_RESPONSE = {
    "skills": ["Python", "FastAPI", "react"],
    "education": [{"title": "Example University", "details": "B.Tech, 2022-2026"}],
    "experience": [{"title": "Backend Intern — Example Co.", "details": "Built APIs."}],
    "projects": [{"title": "Resume Matcher", "details": "Matches resumes to JDs."}],
    "certifications": ["Python for Everybody (Coursera, 2024)"],
}


async def test_extract_resume_with_llm_happy_path(monkeypatch):
    async def fake_generate_json(prompt: str, max_retries: int = 1) -> dict:
        assert "Example resume text" in prompt
        return SAMPLE_LLM_RESPONSE

    monkeypatch.setattr("app.services.resume_ai_parser.generate_json", fake_generate_json)

    parsed = await extract_resume_with_llm("Example resume text with python and docker mentioned.")

    assert parsed.education == [{"title": "Example University", "details": "B.Tech, 2022-2026"}]
    assert parsed.experience[0]["title"] == "Backend Intern — Example Co."
    assert parsed.certifications == ["Python for Everybody (Coursera, 2024)"]
    # skills are lowercased and unioned with the dictionary matcher's own
    # findings in the raw text ("docker" appears in the text but not in the
    # LLM's returned skills list — the union should still catch it).
    assert "python" in parsed.skills
    assert "fastapi" in parsed.skills
    assert "react" in parsed.skills
    assert "docker" in parsed.skills


async def test_extract_resume_with_llm_propagates_unavailable_error(monkeypatch):
    async def fake_generate_json(prompt: str, max_retries: int = 1) -> dict:
        raise LLMUnavailableError("No Gemini API key configured yet.")

    monkeypatch.setattr("app.services.resume_ai_parser.generate_json", fake_generate_json)

    with pytest.raises(LLMUnavailableError):
        await extract_resume_with_llm("Some resume text.")


async def test_extract_resume_with_llm_raises_on_malformed_schema(monkeypatch):
    async def fake_generate_json(prompt: str, max_retries: int = 1) -> dict:
        # Wrong shape entirely — skills should be a list, not a string.
        return {"skills": "python, react", "education": [], "experience": [], "projects": [], "certifications": []}

    monkeypatch.setattr("app.services.resume_ai_parser.generate_json", fake_generate_json)

    with pytest.raises(LLMUnavailableError):
        await extract_resume_with_llm("Some resume text.")
