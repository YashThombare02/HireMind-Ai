"""Curated tech-skills list used for skill extraction. Matched as whole-word/
phrase, case-insensitive substrings against resume/JD text — deliberately
not generic NER (spaCy's default NER doesn't reliably catch terms like
"Redux" or "Kubernetes"; see docs/ARCHITECTURE.md Module 6). Grows as new
sample data / real resumes surface skills it's missing.
"""

import re

# Order matters for multi-word phrases that are substrings of others
# (e.g. "sentence-transformers" must be checked so "transformers" alone
# isn't required) — kept as one flat set since matching is phrase-based,
# not prefix-based, so ordering doesn't actually affect correctness, only
# readability grouped by category below.
SKILLS: set[str] = {
    # Languages
    "python", "javascript", "typescript", "bash",
    # Backend frameworks
    "fastapi", "django", "flask", "express", "node.js", "spring boot",
    # Frontend
    "react", "redux", "next.js", "tailwind css", "html", "css", "jquery",
    # Databases
    "postgresql", "mysql", "mongodb", "sql", "redis",
    # DevOps / infra
    "docker", "kubernetes", "terraform", "aws", "linux", "ci/cd",
    "github actions", "prometheus", "grafana", "nginx",
    # APIs / architecture
    # Single canonical "rest api" (not "rest apis") — the pattern below
    # allows an optional trailing "s", so this one entry matches "REST API",
    # "REST APIs", "REST API design", and "REST API integration" alike.
    # Keeping these as three separate dictionary strings (as an earlier
    # version of this file did) meant a resume's "REST APIs" and a JD's
    # "REST API design" never set-intersected — a real bug caught by the
    # Phase 2 integration test.
    "rest api", "graphql",
    "microservices architecture", "system design",
    # Data / ML / NLP
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch",
    "machine learning", "spacy", "sentence-transformers", "matplotlib",
    "jupyter", "xgboost", "nltk",
    # Messaging / streaming
    "kafka", "socket.io",
    # Testing
    "pytest", "jest", "react testing library",
    # Tools
    "git", "figma", "postman", "chart.js", "recharts",
}

_ESCAPED_SORTED_BY_LENGTH = sorted((re.escape(s) for s in SKILLS), key=len, reverse=True)
# Optional trailing "s" folds simple plurals ("APIs", "certifications") into
# the same canonical singular skill without a second dictionary entry — the
# right-boundary check still applies after it, so "react" still won't match
# inside "reactjs".
_SKILL_PATTERN = re.compile(
    r"(?<![\w-])(" + "|".join(_ESCAPED_SORTED_BY_LENGTH) + r")s?(?![\w-])",
    re.IGNORECASE,
)


def extract_skills(text: str) -> list[str]:
    """Returns the sorted, deduped list of dictionary skills found anywhere
    in `text` (case-insensitive). Longest-phrase-first pattern ordering
    avoids "node.js" only partially matching inside a longer already-matched
    span, etc.
    """
    if not text:
        return []
    found = {match.group(1).lower() for match in _SKILL_PATTERN.finditer(text)}
    return sorted(found)
