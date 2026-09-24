# HireMinds AI — Detailed Architecture Specification

**Purpose of this document:** a complete, module-by-module technical specification of the HireMinds AI system, written to be handed to an architecture-generation tool or a new engineer with no prior context. It covers every part of the system — small utility pieces as well as the major AI modules — including data flow, algorithms, formulas, libraries, database schema, and API surface.

---

## 1. System overview

HireMinds AI is a web platform that takes a candidate's resume and a target job description, and runs them through four connected stages:

1. Resume parsing + job-description matching (ATS scoring)
2. Personalized technical assessment (auto-generated MCQs + coding question)
3. Adaptive AI mock interview (follow-up questions based on prior answers)
4. Cross-modal skill verification — a unifying layer that compares what the candidate *claimed* (resume) against what they *proved* (test + interview), producing a per-skill trust score and flagging mismatches

A secondary research module audits the ATS scoring formula for identity-based bias (does changing a name/college on an otherwise-identical resume change the score).

---

## 2. Tech stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React + Tailwind CSS | Single-page app, no SSR needed |
| Backend | Python + FastAPI | One backend service — no separate Java/Spring service |
| Database | PostgreSQL | Accessed via SQLAlchemy ORM, driver `psycopg` |
| Migrations | Alembic | Every schema change is a versioned migration file, never a manual `ALTER TABLE` |
| Auth | `fastapi-users` + JWT | Library-based, not hand-rolled |
| PDF parsing | PyMuPDF (`fitz`) | Extracts raw text from resume PDFs |
| NLP | spaCy | Section splitting, entity/skill extraction |
| Semantic similarity | Sentence-Transformers (`all-MiniLM-L6-v2`) + `pgvector` | Embeds resume/JD text; vectors stored and compared directly in Postgres via the `pgvector` extension instead of in application code |
| LLM | Gemini free tier (fallback: open-source Hugging Face model) | Question generation, answer evaluation, interview dialogue |
| Charts | Recharts | Candidate performance dashboard |
| Testing | pytest (backend), Jest (frontend) | Unit + integration split |

---

## 3. High-level architecture (layers)

```
Candidate (browser)
   │
   ▼
Frontend — React + Tailwind
   ├─ Pages (upload, JD input, test, interview, dashboard)
   └─ API client (lib/) — attaches JWT, calls backend
   │
   ▼
Backend — Python + FastAPI
   ├─ Auth layer (fastapi-users, JWT)
   ├─ Routers (one file per feature area)
   └─ Services (business logic: parsing, matching, scoring, question generation, interview loop, verification engine)
   │
   ├──▶ PostgreSQL database (all persistent state, incl. resume/JD embeddings via pgvector)
   └──▶ External LLM API (Gemini / Hugging Face) for generation & evaluation calls
```

Design rule carried through every module below: **routers only handle HTTP concerns (validation, auth, request/response shape). All actual logic lives in a `services/` function that the router calls.** This keeps business logic testable without spinning up the HTTP layer.

---

## 4. Database schema

All tables live in one SQLAlchemy `models.py` (split into multiple files only if a single file gets unwieldy, e.g. `models/user.py`, `models/resume.py`, `models/interview.py`).

**Postgres-specific setup:** enable the `pgvector` extension once via migration (`CREATE EXTENSION IF NOT EXISTS vector;`). Semi-structured fields below use `JSONB` (not plain `JSON`) since it's indexable and queryable. Embedding columns use `pgvector`'s `Vector(384)` type (384 = the output dimension of `all-MiniLM-L6-v2`).

### `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID / int PK | |
| name | varchar | |
| email | varchar, unique | |
| hashed_password | varchar | bcrypt via passlib |
| created_at | datetime | |

### `resumes`
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| user_id | FK → users.id | |
| file_path | varchar | where the uploaded PDF is stored |
| raw_text | text | extracted full text |
| skills | JSONB | list of extracted skill strings |
| education | JSONB | list of {degree, institution, year} |
| experience | JSONB | list of {role, company, duration, description} |
| projects | JSONB | list of {title, description, tech_used} |
| certifications | JSONB | list of strings |
| embedding | vector(384) | Sentence-Transformers embedding of `raw_text`, via pgvector |
| created_at | datetime | |

### `job_descriptions`
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| user_id | FK → users.id | who submitted it (candidate or recruiter) |
| title | varchar | |
| raw_text | text | |
| required_skills | JSONB | |
| preferred_skills | JSONB | |
| experience_required | varchar | e.g. "2-4 years" |
| responsibilities | JSONB | list of strings |
| embedding | vector(384) | Sentence-Transformers embedding of `raw_text`, via pgvector |
| created_at | datetime | |

### `ats_results`
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| resume_id | FK | |
| jd_id | FK | |
| match_score | float | 0-100 |
| matched_skills | JSONB | |
| missing_skills | JSONB | |
| experience_relevance | float | |
| recommendation | varchar | short text label |
| created_at | datetime | |

### `tests`
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| jd_id | FK | |
| resume_id | FK | |
| questions | JSONB | list of {id, type: mcq/coding, text, options, correct_answer, skill_tag, test_cases (for coding)} |
| created_at | datetime | |

### `test_attempts`
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| user_id | FK | |
| test_id | FK | |
| answers | JSONB | list of {question_id, answer, is_correct, skill_tag} |
| score | float | |
| started_at / submitted_at | datetime | |

### `interview_sessions`
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| user_id | FK | |
| jd_id | FK | |
| status | enum | `in_progress` / `completed` |
| started_at / ended_at | datetime | |

### `interview_messages`
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| session_id | FK | |
| role | enum | `ai` / `candidate` |
| content | text | |
| skill_tag | varchar, nullable | which skill this exchange probes |
| created_at | datetime | |

### `evaluations`
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| session_id | FK | |
| technical_score | float | |
| communication_score | float | |
| problem_solving_score | float | |
| concept_understanding_score | float | |
| overall_feedback | text | |

### `skill_verification`
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| user_id | FK | |
| skill_name | varchar | |
| resume_claim | boolean | did the resume mention this skill |
| test_score | float, nullable | performance on questions tagged with this skill |
| interview_score | float, nullable | performance on interview exchanges tagged with this skill |
| trust_score | float | combined score, see Module 8 |
| flag | varchar, nullable | e.g. "claimed_but_unverified", "undersold" |

---

## 5. Module: Authentication

**Library:** `fastapi-users` (SQLAlchemy backend) — do not hand-roll password hashing or token issuance.

**Flow:**
1. Signup: `POST /auth/register` — name, email, password → `fastapi-users` hashes password (bcrypt) and creates a `users` row.
2. Login: `POST /auth/jwt/login` — verifies credentials, returns a JWT (short-lived access token, e.g. 60 min expiry).
3. Every protected route depends on `current_active_user` (a FastAPI dependency provided by `fastapi-users`) which decodes and validates the JWT from the `Authorization: Bearer <token>` header.
4. Frontend stores the JWT (in memory / React context — not localStorage, to reduce XSS risk) and attaches it to every API call via the shared `lib/api.ts` client.
5. No refresh tokens, no OAuth/social login, no email verification flow — out of scope, adds complexity with no payoff for a demo project.
6. Password requirements: minimum 8 characters, enforced client-side (basic UX) and server-side (real enforcement) via `fastapi-users`' password validator hook.

**Small things easy to forget:**
- CORS must allow the frontend's origin explicitly (not `*`) since credentials/tokens are involved.
- 401 vs 403: an invalid/expired token → 401. A valid token trying to access someone else's resource → the ownership check (see Module 4-9) returns 404, not 403, so existence of another user's data is never leaked.
- Every query that reads a user-owned row (resume, test attempt, interview session) must filter by `WHERE owner_id = current_user.id` inside the query itself — never fetch-then-check in application code (avoids a race-condition window).

---

## 6. Module: Resume ingestion & parsing

**Endpoint:** `POST /resumes/upload` (multipart file upload, protected route)

**Steps:**
1. Validate: file is a PDF, size ≤ 5MB. Reject otherwise with a clear 400 error.
2. Save the file to disk (or a blob path) and record `file_path`.
3. Extract raw text using PyMuPDF (`page.get_text(sort=True)` — position-sorted, which meaningfully helps multi-column layouts).
4. Clean text: collapse repeated whitespace, blank-line runs, and control characters.
5. **Structure the text into skills/education/experience/projects/certifications via an LLM call** (`app/services/resume_ai_parser.py`), not regex — see "Why LLM, not regex" below. A curated skill dictionary (`app/services/skills_dictionary.py`) also runs independently and is unioned with the LLM's skill list, since it's free, instant, and reliable for known skill names regardless of how the LLM phrases things.
6. **Fallback:** if no LLM is configured yet (`GEMINI_API_KEY` unset) or the LLM call fails/returns unusable JSON after one retry, fall back to `app/services/resume_parser.py`'s regex/keyword-heuristic parser — resume upload never hard-fails just because the LLM step didn't work.
7. Store everything in the `resumes` table.

**Why LLM, not regex (revised from the original design):** the first version of this module was pure regex/keyword heuristics, tested only against this project's own synthetic sample resumes. It broke badly on a real resume using a different (common) template — unrecognized section headings, institution/degree/dates split across lines in a way the parser didn't expect, multi-line certification entries. The fundamental problem isn't a missing pattern to add — arbitrary resume layouts are an open-ended text-understanding problem that a fixed set of rules can't converge on, no matter how many edge cases get patched in. That's exactly the class of problem an LLM generalizes across far better than hand-written rules, so it's the primary path now, with the regex parser kept as a free, always-available fallback (and as what actually runs during local dev before the Gemini key is added).

**Output returned to frontend:** the parsed structured resume (skills list, education, experience, etc.) so the candidate can see what was extracted and optionally correct it before proceeding (small but important trust-building UX step — if parsing gets something wrong, the candidate should be able to see it immediately).

**Edge cases to handle:**
- Scanned/image-only PDFs (no extractable text) — detect this (near-empty extracted text) and show a clear error asking for a text-based PDF, rather than silently proceeding with empty data.
- LLM unavailable or returns malformed JSON — one retry with a stricter prompt, then fall back to the regex parser (see above) rather than failing the request.

---

## 7. Module: Job description analysis

**Endpoint:** `POST /job-descriptions`

**Steps:**
1. Candidate/recruiter pastes plain text (no file upload needed here — much simpler than resume ingestion).
2. Same spaCy + skill-dictionary approach as resumes extracts `required_skills`, `preferred_skills` (distinguished by language cues: "must have" / "required" vs "nice to have" / "preferred" — simple keyword-triggered classification, not a trained classifier).
3. Extract `experience_required` via regex over common patterns ("3+ years", "2-4 years").
4. Store in `job_descriptions`.

---

## 8. Module: Resume–JD matching & ATS scoring

**Endpoint:** `POST /ats/score` (input: resume_id, jd_id)

This is a deliberately **explainable formula**, not a black-box AI decision — important both for user trust and for your paper's bias-audit section (you can't audit a score you can't decompose).

**Sub-scores computed:**
1. **Skill match** — set overlap between resume skills and JD required+preferred skills. `skill_match = |matched_skills| / |required_skills|` (capped at 1.0).
2. **Experience match** — compare years of experience parsed from resume against JD's required years; simple ratio capped at 1.0.
3. **Education match** — does resume's degree/field satisfy JD's stated requirement (simple rule lookup, e.g. B.Tech/B.E in relevant field = full match).
4. **Project relevance** — keyword overlap between project descriptions and JD responsibilities/skills.
5. **Semantic similarity** — embed full resume text and full JD text with Sentence-Transformers (`all-MiniLM-L6-v2`) at upload/submit time, store the vector in the row's `embedding` column (pgvector), and compute similarity with a direct SQL query using pgvector's cosine-distance operator (`embedding <=> :other_embedding`) instead of pulling both vectors into Python — normalized to 0-1.

**Final formula:**
```
match_score = 100 × (
    0.40 × skill_match +
    0.25 × experience_match +
    0.15 × education_match +
    0.10 × project_relevance +
    0.10 × semantic_similarity
)
```

**Output:** `match_score`, `matched_skills`, `missing_skills`, a short textual recommendation (e.g. "Strong match — proceed to assessment" / "Partial match — missing: Docker, GraphQL"). Store in `ats_results`.

---

## 9. Module: Technical assessment generation & evaluation

**Endpoint (generate):** `POST /assessments/generate` (input: resume_id, jd_id)

**Generation steps:**
1. Build a prompt containing: the candidate's extracted skills, the JD's required skills, and an instruction to produce 5 MCQs (each with 4 options, one correct) and 1 coding question, each tagged with which skill it targets.
2. Send to the LLM (Gemini free tier). Parse the response into structured JSON (validate shape — if the LLM's output doesn't parse as expected JSON, retry once with a stricter "return only JSON" instruction before failing).
3. For the coding question, also have the LLM generate 2-3 input/output test case pairs.
4. Store the full question set in `tests`.

**Endpoint (submit):** `POST /assessments/{test_id}/submit`

**Evaluation steps:**
1. MCQs: compare submitted option to `correct_answer` stored in the question JSON — pure string/index comparison, no AI call needed.
2. Coding question: run the submitted code against the stored test cases.
   - Simplest safe approach for a student project: execute in a restricted subprocess with a timeout (e.g. `subprocess.run` with `timeout=5`, no network access, resource limits via `resource` module on Linux or a Docker sandbox if available) — comparing captured stdout to expected output per test case.
   - Do **not** `eval()`/`exec()` submitted code directly in the main process — that's a code-injection risk even in a student demo.
3. Compute overall test score = weighted average (MCQs equally weighted, coding question weighted higher, e.g. 50/50 split between the 5 MCQs combined and the 1 coding question).
4. Store per-question correctness with its `skill_tag` in `test_attempts.answers` — this per-skill breakdown is what Module 8 (verification) reads later.

---

## 10. Module: Adaptive AI mock interview

**Endpoint (start):** `POST /interviews/start` (input: jd_id) → creates an `interview_sessions` row, generates and returns the first question.

**Endpoint (respond):** `POST /interviews/{session_id}/respond` (input: candidate's answer text)

**The interview loop (core logic, lives in `services/interview_engine.py`):**
1. Fetch full conversation history for the session (`interview_messages`, ordered by time).
2. Append the candidate's new answer to history, save it.
3. Build a prompt containing: the JD, the candidate's resume summary, the full conversation history so far, and an instruction: "analyze the last answer; if it lacks depth or contains an interesting claim, ask a targeted follow-up on that specific point; otherwise move to the next topic area."
4. Call the LLM once per turn — this is a **plain bounded loop**, not a LangGraph/agent framework: a `while turn_count < MAX_TURNS` loop, each iteration one LLM call, no more infrastructure than that.
5. Tag the generated question with the skill it's probing (the LLM includes this tag in its structured response, or a simple keyword match against known skills as a fallback).
6. Save the AI's question as a new `interview_messages` row, return it to the frontend.
7. Stop condition: either `MAX_TURNS` reached (e.g. 10 exchanges) or the LLM signals the interview is naturally complete (a specific "stop" token/flag in its structured response).

**Endpoint (end):** `POST /interviews/{session_id}/end` → triggers Module 11 evaluation.

**Small things:**
- Store conversation history as rows, not as one giant blob — makes tagging/scoring per-exchange possible (needed for Module 8).
- Rate-limit interview turns server-side (max turns) to bound LLM cost per session — this is the same reason the cost-control note in the original project report exists.

---

## 11. Module: Interview evaluation

**Trigger:** end-of-interview endpoint.

**Steps:**
1. Send the full conversation transcript to the LLM with an instruction to score: technical knowledge, relevance of answers, problem-solving ability, communication clarity, concept understanding — each 0-10, plus one paragraph of overall feedback.
2. Also compute a per-skill interview score by grouping messages by `skill_tag` and asking the LLM (or a simpler heuristic: answer length + presence of correct technical terms) to score each skill-specific exchange independently — this per-skill number feeds Module 8.
3. Store in `evaluations`.

---

## 12. Module: Cross-modal skill verification (the unique feature)

**Endpoint:** `GET /verification/{user_id}` — computed after resume + test + interview all have data for a shared skill set.

**Per-skill inputs:**
- `resume_claim` (boolean — was this skill listed on the resume)
- `test_score` (0-1, from `test_attempts.answers` filtered by `skill_tag`)
- `interview_score` (0-1, from Module 11's per-skill scoring)

**Trust score formula (draft — refine and write up formally in `plans/skill-verification-scoring.md` before coding):**
```
if resume_claim is True:
    trust_score = 0.5 × test_score + 0.5 × interview_score
    if trust_score < 0.4:
        flag = "claimed_but_unverified"   # resume inflation signal
else:
    trust_score = 0.5 × test_score + 0.5 × interview_score
    if trust_score > 0.7:
        flag = "undersold"                # candidate underselling a real strength
```
(This is a starting point — the exact thresholds and weighting need a short experiment against your hand-labeled dataset before being finalized, per the paper-evaluation plan.)

**Output:** a per-skill table (skill name, resume claim, test score, interview score, trust score, flag) — this is what the dashboard renders, and what the paper's evaluation section measures against ground truth.

---

## 13. Module: Bias/fairness audit (research tool, not a live user feature)

**Not an API endpoint — a standalone script** (`scripts/bias_audit.py`) run manually for paper experiments.

**Steps:**
1. Take a set of real resumes.
2. For each, generate identity-perturbed variants (swap name to signal different gender/ethnicity, swap college name to a different tier) while keeping all substantive content identical.
3. Run each variant through the ATS scoring module (Module 8... i.e. Module 8 in the numbering above, the ATS one).
4. Log `match_score` per variant, compute variance/statistical difference across the identity-perturbed group.
5. Report as a fairness metric (e.g. demographic parity difference) in the paper.

---

## 14. Module: Candidate dashboard / performance report

**Endpoint:** `GET /dashboard/{user_id}` — aggregates: latest ATS result, latest test score, latest interview evaluation, and the full skill-verification table.

**Frontend rendering:**
- Stage-wise score cards (ATS match %, test score %, interview score %)
- A bar chart of matched vs missing skills
- A table of the trust-score-per-skill breakdown, with flags visually highlighted (e.g. a small warning icon next to "claimed_but_unverified" skills)
- One free-text "strengths / weaknesses / suggestions" summary block

---

## 15. Frontend architecture

**Pages (`src/app/`):** `/` (landing), `/signup`, `/login`, `/resume-upload`, `/job-description`, `/ats-results`, `/assessment/:testId`, `/interview/:sessionId`, `/dashboard`.

**Components (`src/components/`):** `Navbar`, `ProtectedRoute` (redirects to `/login` if no valid token in context), `FileUploader`, `McqCard`, `CodeEditorField` (basic textarea, or CodeMirror if time allows), `ChatBubble` (interview UI), `ScoreCard`, `SkillMatchChart`, `TrustScoreTable`.

**API/data layer (`src/lib/`):** one `api.ts` wrapping `fetch`/`axios`, auto-attaching the JWT from an `AuthContext`; one function per backend endpoint (`uploadResume()`, `getAtsScore()`, `submitAssessment()`, `sendInterviewAnswer()`, etc.) — components never call `fetch` directly.

**State:** React context for auth (current user + token). No heavier state library (Redux etc.) needed at this scale.

---

## 16. Backend project structure

```
backend/
  app/
    main.py
    db/
      session.py
      models.py
    auth/
      users.py            (fastapi-users setup)
    routers/
      resume.py
      job_description.py
      ats.py
      assessment.py
      interview.py
      verification.py
      dashboard.py
    services/
      resume_parser.py       (regex/keyword fallback parser)
      resume_ai_parser.py    (LLM-based parser — primary path)
      resume_service.py      (upload orchestration: LLM → fallback → persist)
      llm_client.py           (shared Gemini wrapper: generate_json, LLMUnavailableError)
      jd_analyzer.py
      matcher.py
      assessment_engine.py
      interview_engine.py
      verification_engine.py
    prompts/
      resume_extraction_prompts.py
      assessment_prompts.py
      interview_prompts.py
      evaluation_prompts.py
    config.py              (pydantic-settings, reads .env)
  alembic/
  scripts/
    bias_audit.py
  tests/
    unit/
    integration/
    conftest.py
```

---

## 17. Full API endpoint list

| Method | Path | Purpose | Auth required |
|---|---|---|---|
| POST | /auth/register | Create account | No |
| POST | /auth/jwt/login | Log in, get JWT | No |
| GET | /users/me | Get current user | Yes |
| POST | /resumes/upload | Upload + parse resume | Yes |
| GET | /resumes/{id} | Fetch parsed resume | Yes |
| POST | /job-descriptions | Submit JD | Yes |
| POST | /ats/score | Compute ATS match | Yes |
| GET | /ats/{id} | Fetch ATS result | Yes |
| POST | /assessments/generate | Generate test | Yes |
| POST | /assessments/{test_id}/submit | Submit answers, get score | Yes |
| POST | /interviews/start | Start interview session | Yes |
| POST | /interviews/{session_id}/respond | Send answer, get next question | Yes |
| POST | /interviews/{session_id}/end | End interview, trigger evaluation | Yes |
| GET | /verification/{user_id} | Get skill trust-score table | Yes |
| GET | /dashboard/{user_id} | Get full performance summary | Yes |

Every `{id}`/`{user_id}` route filters by `owner_id = current_user.id` in the SQL query itself, and returns 404 (not 403) if the row doesn't belong to the requester.

---

## 18. Non-functional requirements

- **CORS:** explicit allowed origin (frontend dev URL / deployed URL), not `*`.
- **Error handling:** consistent JSON error shape `{ "detail": "message" }` (FastAPI default) across all routers.
- **Logging:** basic request/error logging to console (no need for a full observability stack).
- **Secrets:** all API keys (LLM provider, DB password) in `.env`, never committed; `.env.example` committed with placeholder values.
- **Rate/cost limits:** cap interview turns and assessment regenerations per session to control LLM API cost.

---

## 19. Testing strategy

- **Unit tests** (`tests/unit/`, no real DB, no real LLM calls — mock the LLM client): ATS scoring formula, skill extraction, MCQ grading, trust-score formula.
- **Integration tests** (`tests/integration/`, real test DB): full resume-upload → parse flow, full auth flow, full interview flow (can mock the LLM call here too to keep tests fast/free, or run a small number of real calls against a cheap model).
- Shared fixtures in `conftest.py` (test DB session, a sample authenticated user, a sample parsed resume).

---

## 20. Deployment/dev environment

- Local dev: `uvicorn app.main:app --reload` for backend, `npm run dev` for frontend, local PostgreSQL instance (or a Docker container running `pgvector/pgvector:pg16`, which ships Postgres with the `pgvector` extension preinstalled — plain `postgres` images need the extension installed separately).
- Free hosted Postgres options for the team to share a single dev/demo database: Neon or Supabase (both support `pgvector` out of the box).
- Driver: `psycopg` (v3) in SQLAlchemy's connection string (`postgresql+psycopg://...`), not `pymysql`/`mysqlclient`.
- No Kubernetes, no Terraform, no multi-service orchestration — single backend process, single frontend dev server, one database.
- Optional: a single `docker-compose.yml` with two services (backend, postgres) for one-command startup, purely for convenience, not required.
