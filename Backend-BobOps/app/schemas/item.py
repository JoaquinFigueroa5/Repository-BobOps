from pydantic import BaseModel, HttpUrl, EmailStr
from uuid import UUID
from typing import Any
from datetime import datetime

# --- Auth schemas ---
class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: UUID
    email: str
    created_at: datetime

# --- Request schemas ---
class RepoRequest(BaseModel):
    github_url: HttpUrl
    session_id: UUID | None = None

class RefactorAnalyzeRequest(BaseModel):
    github_url: HttpUrl | None = None
    session_id: UUID | None = None
    file_path: str | None = None
    language: str = "python"

class RefactorRequest(BaseModel):
    session_id: UUID
    file_path: str
    language: str = "python"

class TestForgeAnalyzeRequest(BaseModel):
    github_url: HttpUrl | None = None
    session_id: UUID | None = None
    file_path: str | None = None
    language: str = "python"
    framework: str = "pytest"  # pytest | jest

class TestForgeResponse(BaseModel):
    session_id: UUID
    module: str = "testforge"
    test_file_path: str
    test_code: str
    tests: list[dict]
    coverage_estimate: float
    edge_cases_found: list[str]
    execution_result: dict | None = None
    tokens_used: int
    chained_from_refactorbot: bool = False

class DocSyncRequest(BaseModel):
    github_url: HttpUrl | None = None
    session_id: UUID | None = None

class DocSyncResponse(BaseModel):
    session_id: UUID
    module: str = "docsync"
    outdated_docs: list[dict]
    updated_docs: list[dict]
    new_docstrings: list[dict]
    changelog_entry: str
    tokens_used: int

class TestForgeRequest(BaseModel):
    session_id: UUID
    file_path: str
    framework: str = "pytest"  # pytest | jest

class BabelDevRequest(BaseModel):
    session_id: UUID
    source_lang: str   # "javascript"
    target_lang: str   # "python"

# --- Response schemas ---
class AnalysisResult(BaseModel):
    session_id: UUID
    module: str
    result: dict[str, Any]
    tokens_used: int

class SessionOut(BaseModel):
    id: UUID
    status: str
    repo_name: str

class RefactorResponse(BaseModel):
    session_id: UUID
    module: str = "refactorbot"
    files_analyzed: list[dict]
    total_issues: int
    issue_summary: dict
    debt_score_before: float
    debt_score_after: float
    tokens_used: int
    chained_from_codelens: bool