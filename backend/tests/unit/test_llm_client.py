import pytest

from app.services.llm_client import LLMUnavailableError, generate_json


async def test_generate_json_raises_when_no_api_key_configured():
    # The test/dev environment deliberately has no GEMINI_API_KEY set yet
    # (see docs/DEV_PLAN.md) — this is the exact case every LLM-calling
    # feature needs a fallback for, so it's worth pinning explicitly rather
    # than only exercising it incidentally through other tests.
    with pytest.raises(LLMUnavailableError):
        await generate_json("any prompt")
