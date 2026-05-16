import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.item import DocSyncRequest, DocSyncResponse
from app.crud.todo import (
    create_repo, create_session, save_analysis, get_session_module_analysis,
    update_session_status,
)
from app.core.auth import get_current_user
from app.models.analysis import User, Repo, Session
from app.services.base_ai_service import AIServiceError
from app.services.ai_factory import ai_service
from app.services.ast_service import ASTService
from app.services.git_service import GitService

router = APIRouter()
ast = ASTService()
git = GitService()


@router.post(
    "/analyze",
    response_model=DocSyncResponse,
    summary="Detecta documentación desactualizada y la regenera automáticamente",
)
async def analyze_docsync(
    body: DocSyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    github_url = None
    session_record = None
    chained = False

    if body.session_id:
        session_record = await db.get(Session, body.session_id)
        if session_record:
            repo_record = await db.get(Repo, session_record.repo_id)
            if repo_record:
                github_url = repo_record.github_url
                chained = True

    if not github_url:
        if body.github_url:
            github_url = str(body.github_url)
        else:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Se requiere github_url o un session_id válido",
            )

    try:
        repo_path = await git.clone(github_url)
    except Exception as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No se pudo clonar el repo: {e}",
        )

    diff_result = await git.get_latest_diff(repo_path.local_path, n_commits=5)
    current_docs = await git.get_current_docs(repo_path.local_path)
    repo_context = await ast.extract_context(str(repo_path.local_path))

    if not diff_result.files_changed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="No hay cambios recientes en el repositorio para analizar",
        )

    if not session_record:
        repo_record = await create_repo(
            db,
            user_id=current_user.id,
            github_url=github_url,
            name=repo_path.name,
            stack_detected=repo_context.get("primary_language"),
            module_map=repo_context.get("structure"),
        )
        session_record = await create_session(
            db, repo_id=repo_record.id, user_id=current_user.id
        )

    code_diff = diff_result.full_diff
    if not code_diff:
        code_diff = diff_result.summary

    try:
        prompt, result, tokens = await ai_service.analyze_for_docsync(
            code_diff=code_diff,
            current_docs=current_docs,
            repo_context=repo_context,
        )
    except AIServiceError as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"El servicio AI no pudo analizar la documentación: {e}",
        )

    outdated_docs = result.get("outdated_docs", [])
    updated_docs = result.get("updated_docs", [])
    new_docstrings = result.get("new_docstrings", [])
    changelog_entry = result.get("changelog_entry", "")

    summary_result = {
        "outdated_docs": outdated_docs,
        "updated_docs": updated_docs,
        "new_docstrings": new_docstrings,
        "changelog_entry": changelog_entry,
        "diff_summary": diff_result.summary,
    }

    await save_analysis(
        db,
        session_id=session_record.id,
        module="docsync",
        context={
            "github_url": github_url,
            "diff_base": diff_result.base_ref,
            "diff_head": diff_result.head_ref,
            "files_changed": len(diff_result.files_changed),
            "docs_found": len(current_docs),
            "chained": chained,
        },
        prompt=prompt,
        result=summary_result,
        tokens=tokens,
    )

    await update_session_status(db, session_record.id, "done")

    return DocSyncResponse(
        session_id=session_record.id,
        outdated_docs=outdated_docs,
        updated_docs=updated_docs,
        new_docstrings=new_docstrings,
        changelog_entry=changelog_entry,
        tokens_used=tokens,
    )


@router.get(
    "/stream/{session_id}",
    summary="Stream de DocSync en tiempo real",
)
async def stream_docsync(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_module_analysis(db, session_id, "docsync")
    return StreamingResponse(
        _stream_docsync_generator(session_id, db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_docsync_generator(session_id: uuid.UUID, db: AsyncSession):
    from app.crud.todo import get_session_with_repo
    session = await get_session_with_repo(db, session_id)
    if not session or not session.repo:
        yield "data: Error: sesión no encontrada\n\n"
        return

    try:
        repo_path = await git.clone(session.repo.github_url)
    except Exception as e:
        yield f"data: Error: {e}\n\n"
        return

    diff_result = await git.get_latest_diff(repo_path.local_path, n_commits=5)
    current_docs = await git.get_current_docs(repo_path.local_path)
    repo_context = await ast.extract_context(str(repo_path.local_path))
    code_diff = diff_result.full_diff or diff_result.summary

    async for chunk in ai_service.stream_docsync(code_diff, current_docs, repo_context):
        yield f"data: {chunk}\n\n"

    yield "data: [DONE]\n\n"


@router.get(
    "/session/{session_id}",
    summary="Recupera el análisis de DocSync de una sesión guardada",
)
async def get_docsync_result(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    analysis = await get_session_module_analysis(db, session_id, "docsync")
    if not analysis:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No se encontró análisis de DocSync para esta sesión",
        )

    result = analysis.result or {}
    return DocSyncResponse(
        session_id=session_id,
        outdated_docs=result.get("outdated_docs", []),
        updated_docs=result.get("updated_docs", []),
        new_docstrings=result.get("new_docstrings", []),
        changelog_entry=result.get("changelog_entry", ""),
        tokens_used=analysis.tokens_used,
    )
