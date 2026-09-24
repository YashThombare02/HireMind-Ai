import pytest


@pytest.fixture
def sample_skills() -> list[str]:
    return ["python", "fastapi", "sql", "react", "docker"]


# DB and authenticated-client fixtures are added in Phase 1 once fastapi-users
# and the async session setup are wired in (see docs/DEV_PLAN.md, Phase 1).
