# HireMinds AI — Detailed Development Plan

This expands the phase overview into concrete, file-level tasks. Each phase lists: what gets built, which files are touched, who owns it (see team split below), and the exact "done" check before moving on.

**Team ownership (recap):**
- **Yash** — tech lead: repo/infra, DB models/migrations, skill-verification engine, dashboard aggregation, bias-audit script, integration
- **Vaibhav** — auth, resume parsing, JD analysis, ATS scoring
- **Aayush** — assessment generation/evaluation, adaptive interview engine
- **Lekhit** — frontend: all pages, components, API integration

---

## Phase 0 — Project setup

**Goal:** everyone can run the whole stack with one command, against an empty but correctly-shaped database.

**Tasks:**
1. Repo scaffold: `backend/`, `frontend/`, `docs/`, `plans/`, `sample_data/` (this phase — done by Claude/Yash).
2. `docker-compose.yml`: three services — `postgres` (pgvector image), `backend` (FastAPI, hot-reload volume mount), `frontend` (Vite dev server, hot-reload volume mount).
3. Backend: `Dockerfile`, `requirements.txt`, `app/config.py` (pydantic-settings reading `.env`), `app/main.py` (FastAPI app + a `/health` endpoint), `app/db/session.py` (SQLAlchemy engine/session).
4. Backend: `app/db/models.py` — all 9 tables from the architecture spec, as SQLAlchemy models. Alembic initialized, first migration generated (`alembic revision --autogenerate -m "initial schema"`) and applied.
5. Frontend: Vite + React + TypeScript + Tailwind scaffold, `Dockerfile`, one placeholder page confirming it can reach `backend`'s `/health` endpoint.
6. `.env.example`, `.gitignore`, root `README.md` with setup instructions.
7. Push initial scaffold to `https://github.com/YashThombare02/HireMind-Ai.git`.

**Done when:** `docker compose up` starts all three containers, `/health` returns 200, the frontend loads and shows "backend connected."

---

## Phase 1 — Auth + skeleton

**Owner:** Vaibhav (backend), Lekhit (frontend)

**Backend tasks:**
- Add `fastapi-users` + SQLAlchemy adapter to `requirements.txt`.
- `app/auth/users.py`: `UserManager`, JWT strategy, `SQLAlchemyUserDatabase`, the `fastapi_users` instance.
- Wire `/auth/register` and `/auth/jwt/login` routers into `main.py`.
- `app/routers/users.py`: `GET /users/me`.

**Frontend tasks:**
- `src/app/signup/`, `src/app/login/` pages with forms.
- `src/lib/AuthContext.tsx` — stores JWT + current user in memory, exposes `login()`/`logout()`/`signup()`.
- `src/components/ProtectedRoute.tsx` — redirects to `/login` if not authenticated.
- `src/lib/api.ts` — base fetch wrapper that attaches `Authorization: Bearer <token>`.

**Done when:** a real signup → login → visiting a protected placeholder `/dashboard` page round-trip works, token persists across page refresh (session-only is fine — no need for long-term persistence yet).

---

## Phase 2 — Resume + JD + ATS

**Owner:** Vaibhub (backend), Lekhit (frontend)

**Backend tasks:**
- `app/services/resume_parser.py`: PDF validation, PyMuPDF text extraction, cleaning, section splitting, spaCy + skill-dictionary extraction.
- `app/routers/resume.py`: `POST /resumes/upload`, `GET /resumes/{id}`.
- `app/services/jd_analyzer.py`: same extraction approach applied to pasted JD text.
- `app/routers/job_description.py`: `POST /job-descriptions`.
- `app/services/matcher.py`: the 5 sub-scores + weighted ATS formula from the spec; Sentence-Transformers embedding generation + pgvector cosine-distance query.
- `app/routers/ats.py`: `POST /ats/score`, `GET /ats/{id}`.
- Skill dictionary: a maintained list/file of known tech skills (`app/services/skills_dictionary.py`) — starts from the sample data's skill set and grows as needed.

**Frontend tasks:**
- `src/app/resume-upload/`: file picker, upload progress, shows parsed-resume preview after upload.
- `src/app/job-description/`: textarea + submit.
- `src/app/ats-results/`: score, matched/missing skill chips, recommendation text.

**Done when:** using a sample resume + sample JD from `sample_data/`, the full flow produces a plausible match score with correct matched/missing skill lists.

---

## Phase 3 — Technical assessment

**Owner:** Aayush (backend), Lekhit (frontend)

**Backend tasks:**
- `app/prompts/assessment_prompts.py`: the generation prompt template.
- `app/services/assessment_engine.py`: calls the LLM client (behind an interface — see note below), parses/validates the returned JSON, retries once on malformed output.
- `app/routers/assessment.py`: `POST /assessments/generate`, `POST /assessments/{test_id}/submit`.
- MCQ grading: direct comparison. Coding grading: sandboxed subprocess execution against stored test cases (timeout-bounded, no `eval`/`exec`).
- **LLM client interface:** `app/services/llm_client.py` — a single function `generate(prompt) -> str` that assessment/interview/verification code calls. Right now (no Gemini key yet) it returns canned/mocked responses from `sample_data/` so the rest of the pipeline is buildable and testable before the key is added. Swapping in the real Gemini call later is a one-file change.

**Frontend tasks:**
- `src/app/assessment/[testId]/`: MCQ rendering, a simple code textarea, submit + score display.

**Done when:** generating a test against a sample resume+JD produces 5 tagged MCQs + 1 tagged coding question (from the mock client for now), submitting produces a scored result with per-skill tags stored.

---

## Phase 4 — Adaptive interview

**Owner:** Aayush (backend), Lekhit (frontend)

**Backend tasks:**
- `app/prompts/interview_prompts.py`.
- `app/services/interview_engine.py`: the bounded loop (`MAX_TURNS`), history fetch/append, follow-up generation, skill tagging, stop condition.
- `app/routers/interview.py`: `POST /interviews/start`, `POST /interviews/{id}/respond`, `POST /interviews/{id}/end`.
- `app/prompts/evaluation_prompts.py` + evaluation logic (Module 11) triggered on end.

**Frontend tasks:**
- `src/app/interview/[sessionId]/`: chat UI (`ChatBubble` component), input box, "end interview" action.

**Done when:** a full mock interview session runs against the mock LLM client end to end, produces varying follow-ups based on mocked "answer quality" signals, and an evaluation record is created on end.

---

## Phase 5 — Skill verification + dashboard

**Owner:** Yash (backend), Lekhit (frontend)

**Backend tasks:**
- Finalize `plans/skill-verification-scoring.md` (the exact formula/thresholds) before touching code.
- `app/services/verification_engine.py`: pulls resume claim + tagged test score + tagged interview score per skill, computes trust score, assigns flags.
- `app/routers/verification.py`: `GET /verification/{user_id}`.
- `app/routers/dashboard.py`: `GET /dashboard/{user_id}` aggregating everything.

**Frontend tasks:**
- `src/app/dashboard/`: score cards, `SkillMatchChart`, `TrustScoreTable` with flag highlighting.

**Done when:** running one sample candidate through the entire pipeline (resume → test → interview) produces a trust-score table with at least one deliberately-planted mismatch correctly flagged.

---

## Phase 6 — Bias audit + paper prep

**Owner:** Yash (script), whole team (data/writing)

**Tasks:**
- `backend/scripts/bias_audit.py`: identity-perturbation + re-scoring + variance logging, run against `sample_data/`.
- Collect/expand the evaluation dataset (real or sourced resumes+JDs, hand-labeled).
- Draft paper method + evaluation sections in parallel.

**Done when:** the bias-audit script produces a logged variance report from at least one real run.

---

## Phase 7 — Integration, testing, demo prep

**Owner:** whole team

**Tasks:**
- Fill unit/integration test gaps per module (see spec's testing section).
- Swap the mock LLM client for the real Gemini call once the API key is added — this is the point where the key gets dropped into `.env`.
- Seed demo data, write and rehearse the demo script.

**Done when:** a full live run (real LLM calls) works end to end without a developer in the loop fixing things live.

---

## Notes on sequencing

- Phases 2 and 3 can start in parallel once Phase 1 is done (Vaibhav and Aayush don't block each other).
- Phase 4 depends on Phase 3's skill-tagging convention being settled first — Aayush should keep both consistent since he owns both.
- Phase 5 depends on Phases 2-4 all producing tagged, storable scores — don't start it early, the data it needs won't exist yet.
- The mock LLM client (Phase 3) is what lets Aayush and Yash build and test everything now, with Gemini added as a drop-in swap at the end — this is exactly why "no API key yet" doesn't block any phase above.
