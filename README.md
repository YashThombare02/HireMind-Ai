# HireMinds AI

AI-powered recruitment platform that analyzes resumes against job descriptions, generates personalized technical assessments, and conducts adaptive AI mock interviews — with a cross-modal system that verifies whether a candidate's claimed skills match what they actually prove in tests and interviews.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system design and [`docs/DEV_PLAN.md`](docs/DEV_PLAN.md) for the phase-by-phase build plan.

## Stack

- Frontend: React + TypeScript + Tailwind CSS
- Backend: Python + FastAPI
- Database: PostgreSQL + pgvector
- LLM: Gemini (added during the testing phase — a mock client is used until then)

## Running locally

1. Copy `.env.example` to `.env` and fill in real values (a working local default is already set for the database).
2. Start everything:

```bash
docker compose up --build
```

3. Backend: http://localhost:8000 (health check at `/health`)
4. Frontend: http://localhost:5173
5. Apply database migrations (first time, and after any schema change):

```bash
docker compose exec backend alembic upgrade head
```

## Project layout

```
backend/    FastAPI app, SQLAlchemy models, Alembic migrations
frontend/   React + Tailwind app
docs/       architecture spec + development plan
plans/      design docs for individual features, written before they're built
sample_data/  sample resumes and job descriptions for local development/testing
```

## Team

| Person | Owns |
|---|---|
| Yash | Infra, DB, skill-verification engine, dashboard, bias audit, integration |
| Vaibhav | Auth, resume parsing, JD analysis, ATS scoring |
| Aayush | Assessment generation/evaluation, adaptive interview |
| Lekhit | Frontend |
