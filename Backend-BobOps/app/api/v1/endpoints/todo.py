from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.item import RepoRequest, AnalysisResult
from app.crud.todo import create_session, save_analysis
from app.services.ai_factory import ai_service

router = APIRouter(prefix="/codelens", tags=["CodeLens"])

@router.post("/analyze", response_model=AnalysisResult)
async def analyze_repo(body: RepoRequest, db: AsyncSession = Depends(get_db)):
    # 1. Crear sesión en la DB
    session = await create_session(db, repo_id=..., user_id=...)

    # 2. Llamar al servicio AI con el contexto del repo
    prompt, result, tokens = await ai_service.analyze_for_codelens(str(body.github_url))

    # 3. Persistir el resultado
    await save_analysis(db, session.id, "codelens", {}, prompt, result, tokens)

    return AnalysisResult(session_id=session.id, module="codelens",
                          result=result, tokens_used=tokens)