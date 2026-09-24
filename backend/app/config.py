from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required — no insecure defaults. Startup fails fast if .env doesn't supply these.
    database_url: str
    jwt_secret: str

    jwt_lifetime_seconds: int = 3600
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    gemini_api_key: str = ""
    # Update this to whatever Gemini's current flash-tier model id is when
    # the API key is actually added — model names/tiers shift over time and
    # this was last checked at the time this line was written, not runtime.
    gemini_model: str = "gemini-1.5-flash"
    llm_timeout_seconds: int = 30

    max_interview_turns: int = 10
    max_resume_size_mb: int = 5
    max_resumes_per_user: int = 20
    max_jd_text_length: int = 10_000
    min_jd_text_length: int = 50

    auth_rate_limit: str = "10/minute"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
