import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.config import settings
from app.db.session import async_session_maker
from app.middleware.logging import RequestLoggingMiddleware
from app.rate_limit import limiter
from app.routers import ats as ats_router
from app.routers import auth as auth_router
from app.routers import job_description as job_description_router
from app.routers import resume as resume_router
from app.routers import users as users_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("hireminds.main")

app = FastAPI(title="HireMinds AI")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_error", extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/health")
async def health():
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception:
        logger.exception("health_check_db_failed")
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "unreachable"})


app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(resume_router.router)
app.include_router(job_description_router.router)
app.include_router(ats_router.router)

# Remaining feature routers are added phase by phase (see docs/DEV_PLAN.md):
# from app.routers import assessment, interview, verification, dashboard
# app.include_router(assessment.router)
# ...
