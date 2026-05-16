from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.analysis import Session, Analysis, Repo, User
from uuid import UUID
import uuid

async def create_repo(db: AsyncSession, user_id: UUID, github_url: str, name: str,
                      stack_detected: str | None = None,
                      module_map: dict | None = None) -> Repo:
    r = Repo(
        id=uuid.uuid4(),
        user_id=user_id,
        github_url=github_url,
        name=name,
        stack_detected=stack_detected,
        module_map=module_map or {},
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r

async def get_or_create_user(db: AsyncSession, supabase_uid: str, email: str) -> User:
    q = await db.execute(select(User).where(User.supabase_uid == supabase_uid))
    user = q.scalar_one_or_none()
    if user:
        return user
    u = User(
        id=uuid.uuid4(),
        supabase_uid=supabase_uid,
        email=email,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u

async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    q = await db.execute(select(User).where(User.id == user_id))
    return q.scalar_one_or_none()

async def create_session(db: AsyncSession, repo_id: UUID, user_id: UUID) -> Session:
    s = Session(id=uuid.uuid4(), repo_id=repo_id, user_id=user_id)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s

async def save_analysis(db: AsyncSession, session_id: UUID, module: str,
                         context: dict, prompt: dict, result: dict, tokens: int) -> Analysis:
    a = Analysis(
        session_id=session_id, module=module,
        input_context=context, bob_prompt=prompt,
        result=result, tokens_used=tokens,
    )
    db.add(a)
    await db.commit()
    return a

async def get_session_analyses(db: AsyncSession, session_id: UUID) -> list[Analysis]:
    q = await db.execute(select(Analysis).where(Analysis.session_id == session_id))
    return q.scalars().all()

async def get_session_module_analysis(db: AsyncSession, session_id: UUID, module: str) -> Analysis | None:
    q = await db.execute(
        select(Analysis).where(Analysis.session_id == session_id, Analysis.module == module)
    )
    return q.scalar_one_or_none()

async def update_session_status(db: AsyncSession, session_id: UUID, status: str) -> None:
    s = await db.get(Session, session_id)
    if s:
        s.status = status
        await db.commit()

async def get_session_with_repo(db: AsyncSession, session_id: UUID) -> Session | None:
    q = await db.execute(
        select(Session)
        .options(selectinload(Session.repo))
        .where(Session.id == session_id)
    )
    return q.scalar_one_or_none()