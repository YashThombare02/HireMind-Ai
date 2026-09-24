# HireMinds AI — Exhaustive, Production-Quality Phase Plan

## Context

Phase 0 (repo scaffold, Docker Compose, DB models, Alembic migration, frontend skeleton, sample dataset) is already built and pushed to `github.com/YashThombare02/HireMind-Ai`. `docs/DEV_PLAN.md` currently has a phase-by-phase plan, but at a coarse grain — it names files to create per phase but doesn't spell out validation rules, error cases, security details, or edge cases.

The user now wants every phase planned to a much finer grain before any more code is written — "production-quality code, student-scale infra" was confirmed explicitly: every endpoint gets real input validation, proper error handling, security basics (rate limiting on auth, file-upload checks, token expiry), structured logging, and full test coverage — but **no** CI/CD, Kubernetes, multi-environment configs, or monitoring stacks, which stay deliberately cut as overkill for a 4-person student project (this matches the earlier "what to skip" decisions already made in this project).

This plan file is the finished deliverable the user asked for. On approval, its content replaces `docs/DEV_PLAN.md` in the repo (verbatim, phase-by-phase), and Phase 1 (auth) implementation begins next.

**Team ownership (unchanged):** Yash — infra/DB/verification engine/dashboard/bias audit/integration. Vaibhav — auth, resume parsing, JD analysis, ATS scoring. Aayush — assessment + interview engines. Lekhit — frontend, all pages/components.

**Conventions used everywhere below (stated once, applies to every phase):**
- Every user-owned row is fetched with `WHERE owner_id = current_user.id` in the query itself; a mismatch returns 404, never 403 (no existence leak) — established in `docs/ARCHITECTURE.md` and enforced starting Phase 1.
- Every POST/PATCH body is a Pydantic model with explicit field constraints (`min_length`, `max_length`, `EmailStr`, etc.) — FastAPI turns violations into 422 automatically; we only hand-write 400/404/409/422/502 for business-logic errors.
- Every router function is thin; logic lives in `services/`, so services are unit-testable without spinning up HTTP.
- Structured logging (Python `logging`, one JSON-ish line per request: method, path, status, duration, user_id if authenticated) via a small FastAPI middleware, added once in Phase 0/1 and used everywhere after. Never log passwords, full resume text, or raw LLM prompts containing PII.
- Global exception handler returns `{"detail": "..."}` for every error path (FastAPI's default shape, used consistently) and logs the real exception server-side without leaking internals to the client.

---

## Phase 0 — Project setup (already built; production-quality deltas to add)

Everything below is additive to the existing scaffold, not a redo.

1. **Config validation fails fast.** `app/config.py`: `jwt_secret` and `database_url` become required (no insecure defaults) — app refuses to start if `.env` is missing them. This matches `SettingsConfigDict(extra="ignore")` guidance: a typo'd env var is silently a no-op, so required fields must be enforced positively, not just defaulted.
2. **CORS origins from config, not hardcoded.** Move the allowed-origins list in `app/main.py` into `settings.cors_origins` (comma-separated env var, parsed to a list), so the frontend URL isn't baked into source.
3. **`/health` checks the database too**, not just "the process is up": attempt a trivial `SELECT 1`, return `{"status": "ok", "db": "ok"}` or a 503 with `{"status": "degraded", "db": "unreachable"}`.
4. **Structured logging middleware** (`app/middleware/logging.py`): logs method, path, status, duration_ms, and user_id (once auth exists) for every request.
5. **Global exception handlers** in `main.py`: one for `RequestValidationError` (422, clean field-level messages), one catch-all for unhandled exceptions (500, generic message to client, full traceback to server log).
6. **`.dockerignore`** for both `backend/` and `frontend/` (exclude `.env`, `__pycache__`, `node_modules`, `.git`) so secrets/bulk never enter the build context.
7. **Lint configs** (code-quality, not CI): `backend/pyproject.toml` with a `[tool.ruff]` section; `frontend/.eslintrc`/`prettier` config. Run manually (`ruff check`, `npm run lint`) — no pipeline automation, matching the agreed student-scale-infra boundary.

**Done when:** `docker compose up`, `/health` returns `{"status": "ok", "db": "ok"}`, a request without a required env var fails to start with a clear error instead of running with a silent default.

---

## Phase 1 — Auth (detailed implementation plan)

### Design decision: custom register/login routes, not `fastapi-users`' auto-mounted routers

`fastapi-users` normally gives you ready-made routers (`get_register_router()`, `get_auth_router()` with `BearerTransport`/`JWTStrategy`) that you `include_router()` as-is. We deliberately **don't** mount those two directly, for two concrete reasons that matter for the "production-quality" bar:

1. **Rate limiting** (`slowapi`) works by decorating a route function with `@limiter.limit(...)`. You can't attach that decorator to a router FastAPI-users builds internally — so register/login need to be routes *we* write.
2. **Request shape control.** `fastapi-users`' default login route expects `OAuth2PasswordRequestForm` (`application/x-www-form-urlencoded`, field named `username` even though it's an email) — an easy footgun for the frontend dev. Writing the route ourselves means it just accepts plain JSON `{email, password}`, which is what every other endpoint in this project accepts.

We still use the library fully for everything else: `UserManager`, password hashing/verification, the `User` model mixin, the JWT strategy, and the `current_active_user` dependency for protected routes. We're only replacing the two thin HTTP-layer routes, not reimplementing auth logic.

One more explicit tradeoff: **no `/auth/logout` endpoint.** Since the JWT is stateless with no server-side blacklist, a "logout" call would do nothing real server-side — implying revocation that doesn't exist would be dishonest, not production-quality. Logout is purely client-side: clear `sessionStorage`, done.

### Files to create/modify

**`backend/requirements.txt`** — add `slowapi==0.13.1`.

**`backend/app/config.py`** — modify:
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str  # now required, no default — startup fails fast if missing
    jwt_secret: str  # now required, no default
    jwt_lifetime_seconds: int = 3600
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    gemini_api_key: str = ""
    max_interview_turns: int = 10

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
```
Removing the insecure defaults on `database_url`/`jwt_secret` is what makes "config validation fails fast" (Phase 0 item) real — Pydantic raises on import if `.env` doesn't supply them.

**`backend/app/schemas/user.py`** (new) — `fastapi-users` Pydantic schemas:
```python
class UserRead(schemas.BaseUser[uuid.UUID]):
    name: str
    created_at: datetime

class UserCreate(schemas.BaseUserCreate):
    name: str

class UserUpdate(schemas.BaseUserUpdate):
    name: str | None = None
```

**`backend/app/auth/users.py`** (new):
```python
async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.jwt_secret
    verification_token_secret = settings.jwt_secret

    async def on_after_register(self, user: User, request: Request | None = None):
        logger.info("user_registered", extra={"user_id": str(user.id)})

async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)

bearer_transport = BearerTransport(tokenUrl="auth/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=settings.jwt_lifetime_seconds)

auth_backend = AuthenticationBackend(name="jwt", transport=bearer_transport, get_strategy=get_jwt_strategy)
fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)
```
No email verification flow (`verification_token_secret` is configured because the library requires it, but we never call the verify endpoints — matches the earlier "no email verification, out of scope" decision).

**`backend/app/routers/auth.py`** (new) — the two hand-written routes:
```python
router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be blank.")
        return v.strip()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/register", response_model=UserRead, status_code=201)
@limiter.limit("10/minute")
async def register(request: Request, payload: RegisterRequest, user_manager=Depends(get_user_manager)):
    try:
        user = await user_manager.create(
            UserCreate(email=payload.email.lower(), password=payload.password, name=payload.name),
            safe=True,
        )
    except UserAlreadyExists:
        raise HTTPException(400, detail="An account with this email already exists.")
    except InvalidPasswordException as exc:
        raise HTTPException(400, detail=str(exc.reason))
    return user

@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    user_manager=Depends(get_user_manager),
    strategy: JWTStrategy = Depends(get_jwt_strategy),
):
    credentials = SimpleNamespace(username=payload.email, password=payload.password)
    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        raise HTTPException(400, detail="Invalid email or password.")
    token = await strategy.write_token(user)
    return TokenResponse(access_token=token)
```
Note on `user_manager.authenticate(...)`: it's typed to accept `OAuth2PasswordRequestForm` but only ever reads `.username`/`.password` off it — a `SimpleNamespace` with those two attributes satisfies it at runtime (Python duck typing), so we don't have to fight the library's form-data assumption just to reuse its password-verification logic.

**`backend/app/routers/users.py`** (new):
```python
router = APIRouter(prefix="/users", tags=["users"])

class UpdateMeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)

@router.get("/me", response_model=UserRead)
async def read_me(user: User = Depends(current_active_user)):
    return user

@router.patch("/me", response_model=UserRead)
async def update_me(payload: UpdateMeRequest, user: User = Depends(current_active_user), user_manager=Depends(get_user_manager)):
    return await user_manager.update(UserUpdate(name=payload.name.strip()), user)
```

**`backend/app/middleware/logging.py`** (new) — the Phase 0 structured-logging item, built now since it's most useful once `user_id` exists:
```python
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        logger.info("request", extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.monotonic() - start) * 1000, 1),
            "user_id": getattr(request.state, "user_id", None),
        })
        return response
```
`current_active_user`'s dependency chain sets `request.state.user_id = str(user.id)` (a one-line addition wrapping the dependency) so authenticated requests show up attributed in the log line.

**`backend/app/main.py`** — modify:
```python
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.exception("unhandled_error", extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

@app.get("/health")
async def health():
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "unreachable"})

app.include_router(auth_router)
app.include_router(users_router)
```

### Testing infrastructure (net-new — `conftest.py` currently has no DB fixtures at all)

**`backend/tests/conftest.py`** additions:
- `test_engine` (session-scoped): points at a separate `hireminds_test` database (same Postgres container — documented as a one-time `CREATE DATABASE hireminds_test;` step in `README.md`'s setup instructions), runs `Base.metadata.create_all` once at session start, drops at session end.
- `db_session` (function-scoped): opens a connection + transaction, yields an `AsyncSession` bound to it, rolls back after each test — so tests never leak state into each other without needing to truncate tables manually.
- `client` (function-scoped): `httpx.AsyncClient` wired to the FastAPI app via `ASGITransport`, with the app's `get_async_session` dependency overridden to yield the test's `db_session`.

This fixture set is what every later phase's integration tests reuse — it's worth getting right now rather than improvising it ad hoc in Phase 2.

**`backend/tests/unit/test_auth_validation.py`:**
- `test_register_rejects_password_under_8_chars`
- `test_register_accepts_password_exactly_8_chars`
- `test_register_rejects_blank_name_after_strip` (e.g. `"   "`)
- `test_login_request_lowercases_email` — actually verify at the route level (see integration tests) since lowercasing happens in the register handler, not the schema; this unit test instead checks the `RegisterRequest`/`LoginRequest` Pydantic validators directly.

**`backend/tests/integration/test_auth.py`:**
- `test_register_then_login_then_get_me` — full happy path, asserts `UserRead` shape and that `GET /users/me` with the returned token succeeds.
- `test_register_duplicate_email_returns_400`
- `test_register_with_short_password_returns_422` (Pydantic-level, before it even reaches `user_manager.create`)
- `test_login_wrong_password_returns_400`
- `test_login_nonexistent_email_returns_400` (same generic message as wrong-password — asserts no enumeration difference)
- `test_get_me_without_token_returns_401`
- `test_get_me_with_garbage_token_returns_401`
- `test_patch_me_updates_name`
- `test_rate_limit_trips_on_burst` — 11 rapid calls to `/auth/register` (with distinct emails so the 11th failure is provably the rate limiter, not `UserAlreadyExists`) within the 1-minute window → 11th response is 429.

### Frontend files

**`frontend/src/lib/api.ts`** — extend:
```ts
export class ApiError extends Error {
  constructor(public status: number, public detail: string) { super(detail); }
}

async function request<T>(path: string, opts: { method?: string; body?: unknown; auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.auth) {
    const token = sessionStorage.getItem("token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail ?? `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const apiGet = <T,>(path: string, auth = false) => request<T>(path, { auth });
export const apiPost = <T,>(path: string, body: unknown, auth = false) => request<T>(path, { method: "POST", body, auth });
export const apiPatch = <T,>(path: string, body: unknown, auth = false) => request<T>(path, { method: "PATCH", body, auth });
```

**`frontend/src/lib/AuthContext.tsx`** (new):
```tsx
type Status = "loading" | "authenticated" | "unauthenticated";
type AuthState = { user: User | null; status: Status };

// On mount: read sessionStorage token; if present, apiGet("/users/me", true) to validate+hydrate;
// on ApiError(401) clear storage and set "unauthenticated"; otherwise set "unauthenticated" immediately.
// login(email, password): apiPost("/auth/login", {...}) -> store token -> apiGet("/users/me", true) -> set user, "authenticated".
// signup(name, email, password): apiPost("/auth/register", {...}) -> immediately call login() so signup doesn't require a second manual login step.
// logout(): sessionStorage.removeItem("token") -> set user null, "unauthenticated".
```
Exposed via a `useAuth()` hook.

**`frontend/src/components/ProtectedRoute.tsx`** (new): `status === "loading"` → spinner; `"unauthenticated"` → `<Navigate to="/login" />`; else render `<Outlet />`.

**`frontend/src/app/signup/SignupPage.tsx`** and **`frontend/src/app/login/LoginPage.tsx`** (new): controlled form fields, client-side checks (email format, password length, signup's confirm-password match) with inline errors, submit disabled while in flight, `ApiError.detail` shown in an error banner on failure, redirect to `/dashboard` on success.

**`frontend/src/app/dashboard/DashboardPage.tsx`** (new placeholder — real content arrives in Phase 5): shows `Welcome, {user.name}` and a logout button, just enough to prove the protected-route round trip works.

**`frontend/src/App.tsx`** — modify: wrap in `<BrowserRouter><AuthProvider>...</AuthProvider></BrowserRouter>`, add routes for `/`, `/signup`, `/login`, and `/dashboard` (the last wrapped in `<ProtectedRoute>`).

### Done when

- `docker compose exec backend pytest tests/` passes, including the rate-limit and ownership/401 cases above.
- Manually: sign up in the browser → redirected to `/dashboard` showing the right name → refresh the page → still logged in (sessionStorage survives reload, cleared only on tab close) → log out → redirected to `/login` → visiting `/dashboard` directly now redirects to `/login`.
- Hitting `/auth/register` 11 times in under a minute (e.g. via `curl` in a loop) returns 429 on the 11th.

---

## Phase 2 — Resume + JD + ATS

**Resume endpoints:**

| Endpoint | Notes |
|---|---|
| `POST /resumes/upload` | multipart PDF upload |
| `GET /resumes/{id}` | fetch parsed resume |
| `PATCH /resumes/{id}` | candidate corrects a parsed field (skills/education/experience/projects/certifications) |
| `GET /resumes/{id}/file` | protected download of the original PDF (never expose raw `file_path` in JSON responses) |

**Upload validation/logic, in order:**
1. Content-type must be `application/pdf`; size ≤ 5MB (`settings.max_resume_size_mb`, both checked — content-type header is spoofable, so it's a first filter, not the real check).
2. Real-PDF check: attempt `fitz.open()` on the bytes; failure → 400 `"File is not a valid PDF."`
3. Save to `backend/uploads/resumes/{uuid}.pdf` (never the user-supplied filename — avoids path traversal; original filename, if kept at all, is stored as metadata only, never used to build a path).
4. Extract text; if extracted length < 50 chars → 422 `"This looks like a scanned/image-only PDF — please upload a text-based PDF."` (no silent proceed-with-empty-data).
5. Clean → **structure via LLM call** (`app/services/resume_ai_parser.py`), skill dictionary run in parallel and unioned in → store. **Revised from the original plan**: this was originally spec'd as pure regex/section-heading heuristics (spaCy + skill-dictionary). That broke badly the first time it hit a real resume using a different template than `sample_data/`'s own — arbitrary resume layouts are an open-ended problem regex can't converge on. LLM-based structuring is now the primary path (`app/services/llm_client.py`, introduced here rather than in Phase 3 as originally planned), with the original regex parser (`app/services/resume_parser.py`) kept as the fallback when no key is configured yet or the LLM call fails — see `docs/ARCHITECTURE.md` Module 6.
6. Soft cap: `MAX_RESUMES_PER_USER` (e.g. 20) — 429/400 past that, prevents storage abuse without needing real infra.
7. Response includes the structured parse **and** the candidate can `PATCH` any field afterward — this is the trust-building "let them fix what parsing got wrong" step flagged as important back when Module 6 was designed.

**Job description endpoints:** `POST /job-descriptions`, `PATCH /job-descriptions/{id}`. Validation: `raw_text` 50-10,000 chars (reject empty/garbage and reject absurdly large pastes). Same extraction + correction pattern as resumes.

**ATS endpoints:** `POST /ats/score`, `GET /ats/{id}`.
- Ownership-checked fetch of both `resume_id` and `jd_id`.
- Idempotency: if a result already exists for this exact resume+jd pair, return it instead of recomputing, unless `force_recompute=true` is passed — avoids redundant embedding computation.
- Formula edge case: if a JD has zero `required_skills` parsed (bad/very short JD), `skill_match` division-by-zero is guarded — falls back to treating skill_match as based on `preferred_skills` only, or 0 with a `recommendation` noting "JD had too few extractable requirements."
- Embeddings computed at resume/JD creation time and stored (`embedding` column); if missing (e.g. older row before a code change), computed lazily on first score request rather than failing.

**Frontend:**
- Resume upload: drag-and-drop + click, client-side pre-check (type/size) before the network call, upload progress, clear distinct error states (wrong type / too large / scanned PDF / server error), an edit view for the parsed fields before "confirm and continue."
- JD page: textarea with a live character counter and min-length hint, same correction pattern.
- ATS results: score with matched (green) / missing (red) skill chips, loading skeleton, retry on failure.

**Tests:**
- Unit: skill/section extraction against `sample_data/ground_truth.json` (assert extracted skills match expected sets within a reasonable tolerance); ATS formula including the zero-required-skills edge case; path-traversal-safe filename generation; LLM extraction (`resume_ai_parser.py`) with `generate_json` mocked, covering the happy path, the no-key/`LLMUnavailableError` path, and a malformed-schema path.
- Integration: upload a real PDF (convert one `sample_data/resumes/*.txt` to PDF for this, per `sample_data/README.md`), full parse → JD → ATS flow against `sample_data`, ownership 404 case, idempotent re-score returns the same result without a second embedding compute (assert via a call count on the embedding function), and one test with `extract_resume_with_llm` mocked end-to-end through the actual upload endpoint to prove the LLM path is really wired in (the dev/test env has no Gemini key, so every *unmocked* test exercises the regex fallback — both paths need explicit coverage).

**Done when:** every sample resume/JD pair from `sample_data/` produces a plausible score, matched/missing skills roughly matching `ground_truth.json`, and the scanned-PDF and oversized-file error paths both trigger correctly with clear messages.

---

## Phase 3 — Technical assessment

**Endpoints:** `POST /assessments/generate`, `POST /assessments/{test_id}/submit`.

**`app/services/llm_client.py` — built in Phase 2, reused here unchanged:**
- `generate_json(prompt, max_retries=1) -> dict`: calls Gemini asking for a JSON response, retries once with a stricter instruction on malformed output, then raises `LLMUnavailableError` (no key configured, or still-malformed after the retry) — timeout-bounded (`settings.llm_timeout_seconds`, 30s default).
- Every caller catches `LLMUnavailableError` and has its own fallback: Phase 2's resume parsing falls back to the regex parser; assessment generation here has no equivalent free fallback, so it instead surfaces a clean 502 `{"detail": "Assessment generation is temporarily unavailable — please try again."}` rather than a raw exception reaching the client.
- LLM output validated against a Pydantic schema (5 MCQs with 4 options + 1 correct index + skill_tag; 1 coding question with 2-3 test cases + skill_tag) — same "validate, retry once, then fail cleanly" shape as `resume_ai_parser.py` uses.

**Generation/submission logic:**
- One active (ungenerated-for again) test per resume+JD pair unless `regenerate=true` explicitly requested — same idempotency pattern as ATS.
- Submission is one-shot: `test_attempts.submitted_at` being already set → a second `POST .../submit` returns 409 `{"detail": "This assessment was already submitted."}`.
- MCQ grading: direct comparison against stored `correct_answer`, no AI call.
- Coding grading: submitted code run in a timeout-bounded (`subprocess.run(..., timeout=5)`) child process against stored test cases, stdout compared to expected output. Never `eval`/`exec` in-process. Documented limitation: isolation is "separate process + timeout" only, not a full container sandbox — acceptable at student scale, explicitly noted rather than silently assumed safe.
- Every question/answer tagged with `skill_tag`, stored per-question in `test_attempts.answers` — this is the data Phase 5's trust score depends on, so it's a hard requirement, not a nice-to-have.

**Frontend:** MCQ + code question rendering, a loading state while generation is in flight (can take several seconds against a real LLM — show progress text, not a frozen screen), submit confirmation, per-question result breakdown after grading, clear "already submitted" state if the user navigates back.

**Tests:**
- Unit: grading logic (MCQ + coding, including a deliberately wrong/timeout-triggering submission), LLM-output schema validation with a fixture of malformed JSON (asserts the retry-then-fail path).
- Integration: full generate → submit flow against the mock client using `sample_data`; double-submit → 409; malformed mock response triggers the retry path (a second fixture can simulate this).

**Done when:** a test generated from any `sample_data` resume+JD pair has 5 tagged MCQs + 1 tagged coding question, grading produces a per-skill breakdown, and a double-submit is rejected cleanly.

---

## Phase 4 — Adaptive interview

**Endpoints:** `POST /interviews/start`, `POST /interviews/{id}/respond`, `POST /interviews/{id}/end`.

**Loop logic (`app/services/interview_engine.py`):** bounded `while turn_count < MAX_TURNS` loop (server-enforced even if a client tried to send more — defense in depth, not just a frontend limit), one LLM call per turn via the same hardened `llm_client`, history fetched/appended per turn, each AI question tagged with `skill_tag`.

**Validation/state handling:**
- `respond` on a session not in `in_progress` status → 409 `{"detail": "This interview session has already ended."}`
- Candidate answer: min length (e.g. 10 chars, reject empty/whitespace-only) and a sane max length (e.g. 5,000 chars) to bound prompt size/cost.
- Session ownership check (404 pattern) on every call.
- **Lazy abandonment handling** (no background job queue, so this is checked on read, not on a schedule): if a session's last message is older than e.g. 2 hours and status is still `in_progress`, treat it as abandoned on next access — auto-mark `ended` with a note, rather than leaving orphaned in-progress sessions forever.

**Frontend:** chat UI (`ChatBubble`), typing indicator while awaiting the AI's next question, input disabled while waiting, auto-scroll, live character counter, confirmation dialog before ending, graceful network-error retry (don't lose the candidate's typed answer on a failed request).

**Tests:**
- Unit: loop stop condition at `MAX_TURNS` with a mocked LLM that never signals "done" (proves the server-side cap actually bites); lazy-abandonment logic with a fabricated old timestamp.
- Integration: full session lifecycle against the mock client; respond-after-end → 409; ownership 404.

**Done when:** a full mock interview runs start to end against the mock client, visibly varies its follow-ups based on mocked answer-quality signals, stops at `MAX_TURNS` even if forced, and an `evaluations` row is created on end.

---

## Phase 5 — Skill verification + dashboard

**Endpoints:** `GET /verification/{user_id}`, `GET /dashboard/{user_id}`.

**Trust-score computation trigger — event-driven, not lazy-on-every-request:** recompute and upsert into `skill_verification` whenever new tagged data arrives (a test is submitted, or an interview ends) — not recalculated on every dashboard load. This keeps `GET /dashboard` a fast read of already-stored rows, and matches the "production-quality, don't do wasted recompute" bar the user asked for.

**Formula:** exactly as drafted in `plans/skill-verification-scoring.md` (0.5×test + 0.5×interview when both exist, fall back to whichever exists, null when neither exists — no flag when null). Thresholds (0.4 / 0.7) are placeholders per that doc, to be tuned once real runs exist.

**Regression test built into this phase, not deferred:** running `sample_data/resumes/06_karan_kapoor_inflated_resume.txt` through the full pipeline (mock test + mock interview scored deliberately low on its 7 inflated skills) must produce `claimed_but_unverified` flags on those 7 skills and no flag on `python`/`fastapi`/`docker` — this is exactly the scenario `ground_truth.json` and `plans/skill-verification-scoring.md` were built for, and it's the check that proves the feature works before trusting it on a real candidate.

**Dashboard aggregation:** must degrade gracefully when a candidate hasn't completed every stage yet (e.g. no interview done yet → that section shows a clear "not started" state, not an error or a crash on a missing join).

**Frontend:** stage-wise score cards, `SkillMatchChart`, `TrustScoreTable` with flags visually called out (icon + a plain-language tooltip explaining what "claimed_but_unverified" means — this is presentation-facing for your guide/demo, worth getting right), empty states per incomplete stage.

**Tests:**
- Unit: trust-score formula across all null/partial/full-data branches.
- Integration: the Karan Kapoor regression scenario above, end to end, asserted against `ground_truth.json`'s `inflated_skills` list.

**Done when:** the Karan Kapoor regression case produces exactly the expected flags, and a dashboard for a candidate who's only done the resume+ATS stage renders cleanly with "not started" states for test/interview instead of erroring.

---

## Phase 6 — Bias audit + paper prep

**`backend/scripts/bias_audit.py`:** re-runnable/idempotent, takes resumes (starting with `sample_data/`), generates identity-perturbed variants (name, college tier) with substantive content unchanged, re-scores each via the same `app/services/matcher.py` used in Phase 2 (no duplicated scoring logic), and writes a structured report (JSON or CSV, not just stdout prints) with per-variant scores and computed variance — so results feed directly into the paper's evaluation section rather than needing to be re-transcribed by hand.

**Done when:** one real run against `sample_data` produces a saved report file with a computed score-variance number.

---

## Phase 7 — Hardening, full test pass, demo prep

- Full test-suite gap-fill against the testing strategy in `docs/ARCHITECTURE.md` §19 — every unit/integration test named in Phases 1-6 above actually exists and passes.
- **Security review checklist** (a real pass, not just a mention): CORS origins locked to the actual deployed/dev frontend URL; `.env` confirmed never committed (`git log --all -- .env` should be empty); no raw/string-concatenated SQL anywhere (SQLAlchemy ORM used throughout — grep for `execute(f"` or similar as a sanity check); no `dangerouslySetInnerHTML` on the frontend; rate limiting active on auth; file-upload validation active; logs contain no passwords/full resume text/raw prompts with PII.
- Swap the mock LLM client for the real Gemini call (one-file change in `llm_client.py`) once the API key is added to `.env` — this is the point that key gets used, as planned from the start.
- `backend/scripts/seed_demo_data.py`: loads `sample_data/` resumes + job descriptions into the database for a demo account, so the demo doesn't start from an empty state.
- Rehearse the demo script end to end with real (not mocked) LLM calls at least once before presenting.

**Done when:** a full live run (real Gemini calls, seeded demo data) works end to end without a developer intervening, and the security checklist above is fully checked off.

---

## Sequencing (updated: `llm_client.py` now lands in Phase 2, not Phase 3)

Phases 2 and 3 can run in parallel once Phase 1 lands (Vaibhav and Aayush don't block each other). Phase 4 depends on Phase 3's skill-tagging convention (same owner, so it stays consistent). Phase 5 depends on Phases 2-4 all producing tagged, storable scores — don't start it early. `app/services/llm_client.py` (`generate_json` + `LLMUnavailableError`) was built in Phase 2 for resume parsing, earlier than originally planned — Phase 3 onward reuse it unchanged. Every LLM-calling feature has its own fallback for "no key configured yet" (Phase 2: the regex parser; Phase 3+: a clean 502 rather than a raw exception), which is what makes "no Gemini key yet" a non-blocker for every phase.

## Verification

Each phase's own "Done when" line above is the acceptance check for that phase — run it before moving to the next. At the end of Phase 7, the full check is: `docker compose up`, run the seed script, walk through resume upload → JD → ATS → assessment → interview → dashboard for a seeded demo candidate with real LLM calls, and confirm the Karan-Kapoor-style flagging behavior on a resume with deliberately inflated skills — plus a clean `pytest` run (`docker compose exec backend pytest`) and a clean `ruff check` / `npm run lint`.

## Execution note

On approval, this file's content is written into `docs/ARCHITECTURE.md`-adjacent `docs/DEV_PLAN.md` (replacing its current, coarser version) and committed/pushed, then Phase 1 (auth) implementation begins.
