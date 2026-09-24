from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://hireminds:hireminds_dev_password@localhost:5432/hireminds"
    jwt_secret: str = "change_this_to_a_long_random_string"
    gemini_api_key: str = ""

    max_interview_turns: int = 10


settings = Settings()
