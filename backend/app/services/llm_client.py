"""Thin wrapper around the Gemini API for JSON-structured generation, shared
by every feature that needs an LLM call (resume structuring now; assessment
generation, interview, and evaluation in later phases).

Not yet exercised against the real API — GEMINI_API_KEY is deliberately
unset until the testing phase (see docs/DEV_PLAN.md). Until it's set,
`generate_json` raises LLMUnavailableError immediately; every caller of this
module is expected to have a non-LLM fallback for that case rather than
treating it as a hard failure (see resume_ai_parser.py for the pattern).
"""

import asyncio
import json
import logging

from app.config import settings

logger = logging.getLogger("hireminds.llm")

_model = None


class LLMUnavailableError(Exception):
    """No LLM provider is configured, or it never returned usable JSON
    after retrying. Not a bug to fix at the call site — callers with a
    fallback should catch this and use it.
    """


def _get_model():
    global _model
    if _model is None:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        _model = genai.GenerativeModel(settings.gemini_model)
    return _model


async def generate_json(prompt: str, max_retries: int = 1) -> dict:
    """Calls the LLM asking for a JSON response and parses it. Retries once
    with a stricter instruction if the first response isn't valid JSON,
    then raises LLMUnavailableError rather than returning something the
    caller would have to defensively re-validate anyway.
    """
    if not settings.gemini_api_key:
        raise LLMUnavailableError("No Gemini API key configured yet.")

    model = _get_model()
    attempt_prompt = prompt
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = await asyncio.wait_for(
                model.generate_content_async(
                    attempt_prompt,
                    generation_config={"response_mime_type": "application/json"},
                ),
                timeout=settings.llm_timeout_seconds,
            )
            return json.loads(response.text)
        except Exception as exc:
            # Deliberately broad: provider errors, network errors, and JSON
            # parse errors are all handled identically here (retry, then
            # let the caller fall back) — no value in distinguishing them.
            last_error = exc
            logger.warning("llm_generate_json_failed", extra={"attempt": attempt, "error": str(exc)})
            attempt_prompt = (
                f"{prompt}\n\nYour previous response was not valid JSON. "
                "Return ONLY valid JSON matching the schema above — no markdown fences, no commentary."
            )

    raise LLMUnavailableError(f"LLM did not return valid JSON after {max_retries + 1} attempts: {last_error}")
