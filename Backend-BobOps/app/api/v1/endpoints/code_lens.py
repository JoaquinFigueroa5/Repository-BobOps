"""
api/v1/endpoints/codelens.py

Endpoint completo de CodeLens.
Muestra cómo se conectan: router → schema → crud → bob_service → db
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.item import RepoRequest, AnalysisResult
from app.crud.todo import create_repo, create_session, save_analysis, get_session_analyses, get_session_with_repo
from app.core.auth import get_current_user
from app.models.analysis import User
from app.services.base_ai_service import AIServiceError
from app.services.ai_factory import ai_service
from app.services.ast_service import ASTService
from app.services.git_service import GitService

router = APIRouter()
ast    = ASTService()
git    = GitService()


@router.post(
    "/analyze",
    response_model=AnalysisResult,
    summary="Analiza un repo y genera el tour de CodeLens",
)
async def analyze_repo(
    body: RepoRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Flujo completo:
    1. Clonar el repo con GitPython
    2. Parsear estructura con tree-sitter (ASTService)
    3. Enviar contexto a IBM Bob
    4. Guardar resultado en DB
    5. Retornar el análisis al frontend
    """
    if not current_user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        repo_path = await git.clone(str(body.github_url))
    except Exception as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"No se pudo clonar el repo: {e}")

    repo_context = await ast.extract_context(str(repo_path.local_path))

    repo_record = await create_repo(
        db,
        user_id=current_user.id,
        github_url=str(body.github_url),
        name=repo_path.name,
        stack_detected=repo_context.get("primary_language"),
        module_map=repo_context.get("structure"),
    )

    session = await create_session(db, repo_id=repo_record.id, user_id=current_user.id)

    try:
        prompt, result, tokens = await ai_service.analyze_for_codelens(repo_context)
    except AIServiceError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            detail=f"El servicio AI no pudo analizar el repo: {e}")

    await save_analysis(
        db,
        session_id=session.id,
        module="codelens",
        context=repo_context,
        prompt=prompt,
        result=result,
        tokens=tokens,
    )

    return AnalysisResult(
        session_id=session.id,
        module="codelens",
        result=result,
        tokens_used=tokens,
    )


@router.get(
    "/stream/{session_id}",
    summary="Stream de CodeLens en tiempo real (para la demo)",
)
async def stream_codelens(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await get_session_with_repo(db, session_id)
    if not session or not session.repo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada")

    repo_path    = await git.clone(session.repo.github_url)
    repo_context = await ast.extract_context(str(repo_path.local_path))

    return StreamingResponse(
        ai_service.stream_codelens(repo_context),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/session/{session_id}",
    summary="Recupera el análisis de CodeLens de una sesión guardada",
)
async def get_codelens_result(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Útil para cachear: si el repo ya fue analizado, no vuelve a llamar a Bob.
    """
    analyses = await get_session_analyses(db, session_id)
    codelens  = next((a for a in analyses if a.module == "codelens"), None)

    if not codelens:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail="No se encontró análisis de CodeLens para esta sesión")

    return AnalysisResult(
        session_id=session_id,
        module="codelens",
        result=codelens.result,
        tokens_used=codelens.tokens_used,
    )