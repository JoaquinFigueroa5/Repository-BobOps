from sqlalchemy import String, ForeignKey, JSON, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.db.base import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    supabase_uid: Mapped[uuid.UUID] = mapped_column(UUID, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    repos: Mapped[list["Repo"]] = relationship(back_populates="user")

class Repo(Base):
    __tablename__ = "repos"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    github_url: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    stack_detected: Mapped[str] = mapped_column(String, nullable=True)
    module_map: Mapped[dict] = mapped_column(JSON, default={})
    user: Mapped["User"] = relationship(back_populates="repos")
    sessions: Mapped[list["Session"]] = relationship(back_populates="repo")

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repos.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String, default="running")  # running|done|error
    repo: Mapped["Repo"] = relationship(back_populates="sessions")
    analyses: Mapped[list["Analysis"]] = relationship(back_populates="session")

class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"))
    module: Mapped[str] = mapped_column(String)  # codelens|refactorbot|testforge|docsync|babeldev
    input_context: Mapped[dict] = mapped_column(JSON)
    bob_prompt: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON, nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    session: Mapped["Session"] = relationship(back_populates="analyses")