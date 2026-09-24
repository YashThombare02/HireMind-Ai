import uuid
from datetime import datetime

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 384  # output size of the all-MiniLM-L6-v2 sentence-transformer


class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    raw_text: Mapped[str] = mapped_column(Text)
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    education: Mapped[list] = mapped_column(JSONB, default=list)
    experience: Mapped[list] = mapped_column(JSONB, default=list)
    projects: Mapped[list] = mapped_column(JSONB, default=list)
    certifications: Mapped[list] = mapped_column(JSONB, default=list)
    embedding: Mapped[list | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    raw_text: Mapped[str] = mapped_column(Text)
    required_skills: Mapped[list] = mapped_column(JSONB, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSONB, default=list)
    experience_required: Mapped[str | None] = mapped_column(String(50), nullable=True)
    responsibilities: Mapped[list] = mapped_column(JSONB, default=list)
    embedding: Mapped[list | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AtsResult(Base):
    __tablename__ = "ats_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    resume_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resumes.id"), index=True)
    jd_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_descriptions.id"), index=True)
    match_score: Mapped[float]
    matched_skills: Mapped[list] = mapped_column(JSONB, default=list)
    missing_skills: Mapped[list] = mapped_column(JSONB, default=list)
    experience_relevance: Mapped[float | None] = mapped_column(nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Test(Base):
    __tablename__ = "tests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    jd_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_descriptions.id"), index=True)
    resume_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resumes.id"), index=True)
    # each item: {id, type: "mcq"|"coding", text, options, correct_answer, skill_tag, test_cases}
    questions: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id"), index=True)
    # each item: {question_id, answer, is_correct, skill_tag}
    answers: Mapped[list] = mapped_column(JSONB, default=list)
    score: Mapped[float | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    jd_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_descriptions.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress | completed
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)


class InterviewMessage(Base):
    __tablename__ = "interview_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # "ai" | "candidate"
    content: Mapped[str] = mapped_column(Text)
    skill_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    technical_score: Mapped[float | None] = mapped_column(nullable=True)
    communication_score: Mapped[float | None] = mapped_column(nullable=True)
    problem_solving_score: Mapped[float | None] = mapped_column(nullable=True)
    concept_understanding_score: Mapped[float | None] = mapped_column(nullable=True)
    overall_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)


class SkillVerification(Base):
    __tablename__ = "skill_verification"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    skill_name: Mapped[str] = mapped_column(String(100))
    resume_claim: Mapped[bool] = mapped_column(default=False)
    test_score: Mapped[float | None] = mapped_column(nullable=True)
    interview_score: Mapped[float | None] = mapped_column(nullable=True)
    trust_score: Mapped[float | None] = mapped_column(nullable=True)
    flag: Mapped[str | None] = mapped_column(String(50), nullable=True)
