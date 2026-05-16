"""
api/v1/endpoints/refactorbot.py

RefactorBot: detecta anti-patterns, código duplicado y funciones complejas.
Se encadena con CodeLens (usa sus complexity_hotspots) o funciona standalone.
"""

import uuid
import difflib
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.item import RefactorAnalyzeRequest, RefactorResponse
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

LANGUAGE_MAP = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go", ".rb": "ruby", ".java": "java",
    ".rs": "rust", ".cpp": "cpp", ".c": "c",
}


@router.post(
    "/analyze",
    response_model=RefactorResponse,
    summary="Analiza y refactoriza código encadenado desde CodeLens o standalone",
)
async def analyze_refactor(
    body: RefactorAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    # ── 1. Resolver github_url y session ──────────────────────────────────
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
                detail="Se requiere github_url o un session_id válido de CodeLens",
            )

    # ── 2. Clonar repo ────────────────────────────────────────────────────
    try:
        repo_path = await git.clone(github_url)
    except Exception as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No se pudo clonar el repo: {e}",
        )

    # ── 3. Obtener lista de archivos a refactorizar ───────────────────────
    files_to_refactor = []

    if body.file_path:
        files_to_refactor.append({"path": body.file_path, "language": body.language})

    elif chained and session_record:
        codelens_analysis = await get_session_module_analysis(db, body.session_id, "codelens")
        if codelens_analysis and codelens_analysis.input_context:
            hotspots = codelens_analysis.input_context.get("complexity_hotspots", [])
            if hotspots:
                for h in hotspots[:10]:
                    ext = "." + h["path"].rsplit(".", 1)[-1] if "." in h["path"] else ""
                    files_to_refactor.append({
                        "path": h["path"],
                        "language": LANGUAGE_MAP.get(ext, h.get("language", "python")),
                    })

    if not files_to_refactor:
        repo_context = await ast.extract_context(str(repo_path.local_path))
        hotspots = repo_context.get("complexity_hotspots", [])
        if hotspots:
            for h in hotspots[:10]:
                ext = "." + h["path"].rsplit(".", 1)[-1] if "." in h["path"] else ""
                files_to_refactor.append({
                    "path": h["path"],
                    "language": LANGUAGE_MAP.get(ext, h.get("language", "python")),
                })

    if not files_to_refactor:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No se encontraron archivos para refactorizar",
        )

    # ── 4. Crear session si no existe ─────────────────────────────────────
    if not session_record:
        repo_record = await create_repo(
            db,
            user_id=current_user.id,
            github_url=github_url,
            name=repo_path.name,
            stack_detected="unknown",
            module_map={},
        )
        session_record = await create_session(
            db, repo_id=repo_record.id, user_id=current_user.id
        )

    # ── 5. Refactorizar archivo por archivo ───────────────────────────────
    all_issues = []
    all_refactored = []
    total_tokens = 0
    debt_before = 0.0
    debt_after = 0.0

    for item in files_to_refactor:
        try:
            code = await git.read_file(repo_path.local_path, item["path"])
        except Exception:
            continue

        try:
            prompt, result, tokens = await ai_service.analyze_for_refactorbot(
                file_path=item["path"],
                language=item["language"],
                code=code,
                module_context={
                    "repo": github_url,
                    "total_files": len(files_to_refactor),
                },
            )
        except AIServiceError:
            continue

        issues = result.get("issues", [])
        all_issues.extend(issues)
        total_tokens += tokens

        metrics = result.get("metrics", {})
        debt_before += metrics.get("complexity_before", 0)
        debt_after += metrics.get("complexity_after", 0)

        code_lines = code.splitlines()
        for issue in issues:
            issue.setdefault("effort", "medium")
            issue.setdefault("impact", "medium")
            start = max(0, issue.get("line_start", 1) - 1)
            end = issue.get("line_end", start + 1)
            snippet_lines = code_lines[start:end]
            issue["snippet"] = "\n".join(snippet_lines)

        refactored = result.get("refactored_code", "")
        diff = ""
        if refactored:
            original_lines = code.splitlines(keepends=True)
            refactored_lines = refactored.splitlines(keepends=True)
            diff = "".join(difflib.unified_diff(
                original_lines, refactored_lines,
                fromfile=f"a/{item['path']}",
                tofile=f"b/{item['path']}",
                lineterm="\n",
            ))

        all_refactored.append({
            "path": item["path"],
            "issues": issues,
            "refactored_code": refactored,
            "diff": diff or result.get("diff", ""),
            "changes_explanation": result.get("changes_explanation", []),
            "metrics": metrics,
            "debt_score": result.get("debt_score", 0),
            "impact_analysis": result.get("impact_analysis", {}),
        })

        await save_analysis(
            db,
            session_id=session_record.id,
            module=f"refactorbot:{item['path']}",
            context={"file_path": item["path"], "language": item["language"]},
            prompt=prompt,
            result=result,
            tokens=tokens,
        )

    # ── 6. Guardar resumen en DB ──────────────────────────────────────────
    if not session_record:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No session")

    issue_summary = {}
    for issue in all_issues:
        t = issue.get("type", "other")
        if t not in issue_summary:
            issue_summary[t] = {"count": 0, "severities": {}}
        issue_summary[t]["count"] += 1
        sev = issue.get("severity", "low")
        issue_summary[t]["severities"][sev] = issue_summary[t]["severities"].get(sev, 0) + 1

    summary_result = {
        "files_analyzed": all_refactored,
        "total_issues": len(all_issues),
        "issue_summary": issue_summary,
        "debt_score_before": round(debt_before / max(len(all_refactored), 1), 2),
        "debt_score_after": round(debt_after / max(len(all_refactored), 1), 2),
    }

    await save_analysis(
        db,
        session_id=session_record.id,
        module="refactorbot",
        context={
            "github_url": github_url,
            "files_requested": len(files_to_refactor),
            "chained_from_codelens": chained,
        },
        prompt={},
        result=summary_result,
        tokens=total_tokens,
    )

    await update_session_status(db, session_record.id, "done")

    return RefactorResponse(
        session_id=session_record.id,
        files_analyzed=all_refactored,
        total_issues=len(all_issues),
        issue_summary=issue_summary,
        debt_score_before=round(debt_before / max(len(all_refactored), 1), 2),
        debt_score_after=round(debt_after / max(len(all_refactored), 1), 2),
        tokens_used=total_tokens,
        chained_from_codelens=chained,
    )


@router.get(
    "/stream/{session_id}",
    summary="Stream de RefactorBot en tiempo real para un archivo específico",
)
async def stream_refactorbot(
    session_id: uuid.UUID,
    github_url: str,
    file_path: str,
    language: str = "python",
):
    repo_path = await git.clone(github_url)
    code = await git.read_file(repo_path.local_path, file_path)

    return StreamingResponse(
        ai_service.stream_refactorbot(file_path, language, code, {"repo": github_url}),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/session/{session_id}",
    summary="Recupera el análisis de RefactorBot de una sesión guardada",
)
async def get_refactorbot_result(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    analysis = await get_session_module_analysis(db, session_id, "refactorbot")
    if not analysis:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No se encontró análisis de RefactorBot para esta sesión",
        )

    result = analysis.result or {}
    return RefactorResponse(
        session_id=session_id,
        files_analyzed=result.get("files_analyzed", []),
        total_issues=result.get("total_issues", 0),
        issue_summary=result.get("issue_summary", {}),
        debt_score_before=result.get("debt_score_before", 0),
        debt_score_after=result.get("debt_score_after", 0),
        tokens_used=analysis.tokens_used,
        chained_from_codelens=analysis.input_context.get("chained_from_codelens", False),
    )
