from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="HireMinds AI")

# Dev-only origins for the Vite frontend. Tighten this before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Feature routers are added phase by phase (see docs/DEV_PLAN.md):
# from app.routers import resume, job_description, ats, assessment, interview, verification, dashboard
# app.include_router(resume.router)
# ...
