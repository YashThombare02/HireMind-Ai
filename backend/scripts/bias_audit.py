"""Bias/fairness audit for the ATS scoring formula.

Not a live API — a standalone script for paper experiments (Phase 6, see
docs/DEV_PLAN.md). Takes resumes, generates identity-perturbed variants
(name, college tier) with substantive content unchanged, re-runs each
through app.services.matcher, and logs match_score variance across variants.

Left as a stub until Phase 6 — the ATS matcher it depends on is built in
Phase 2.
"""

if __name__ == "__main__":
    raise SystemExit("Not implemented yet — see docs/DEV_PLAN.md, Phase 6.")
