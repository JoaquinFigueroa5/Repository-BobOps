import asyncio
import json
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.item import TestForgeAnalyzeRequest, TestForgeResponse
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

TIMEOUT_SECONDS = 60


@router.post(
    "/analyze",
    response_model=TestForgeResponse,
    summary="Genera tests automáticos y los ejecuta para obtener cobertura real",
)
async def analyze_testforge(
    body: TestForgeAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    github_url = None
    session_record = None
    chained = False
    language = body.language
    file_path = body.file_path
    framework = body.framework

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

    files_to_test = []

    if file_path:
        files_to_test.append({"path": file_path, "language": language, "framework": framework})
    elif chained and session_record:
        refactor_analysis = await get_session_module_analysis(db, body.session_id, "refactorbot")
        if refactor_analysis and refactor_analysis.result:
            files_data = refactor_analysis.result.get("files_analyzed", [])
            if files_data:
                for f in files_data[:5]:
                    fp = f.get("path", "")
                    ext = "." + fp.rsplit(".", 1)[-1] if "." in fp else ""
                    lang = LANGUAGE_MAP.get(ext, "python")
                    fw = "pytest" if lang == "python" else "jest"
                    files_to_test.append({"path": fp, "language": lang, "framework": fw})

    if not files_to_test:
        repo_context = await ast.extract_context(str(repo_path.local_path))
        files_list = repo_context.get("files", [])
        code_files = [f for f in files_list if f.get("path", "").endswith((".py", ".js", ".jsx", ".ts", ".tsx"))]
        for f in code_files[:5]:
            fp = f["path"]
            ext = "." + fp.rsplit(".", 1)[-1] if "." in fp else ""
            lang = LANGUAGE_MAP.get(ext, "python")
            fw = "pytest" if lang == "python" else "jest"
            files_to_test.append({"path": fp, "language": lang, "framework": fw})

    if not files_to_test:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No se encontraron archivos de código para generar tests",
        )

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

    all_tests = []
    total_tokens = 0
    combined_coverage = 0.0
    combined_execution = {"passed": 0, "failed": 0, "coverage": 0.0}
    file_count = 0

    for item in files_to_test:
        try:
            code = await git.read_file(repo_path.local_path, item["path"])
        except Exception:
            continue

        try:
            prompt, result, tokens = await ai_service.analyze_for_testforge(
                file_path=item["path"],
                language=item["language"],
                code=code,
                module_context={
                    "repo": github_url,
                    "framework": item["framework"],
                    "total_files": len(files_to_test),
                },
            )
        except AIServiceError:
            continue

        total_tokens += tokens
        file_count += 1

        test_code = result.get("test_code", "")
        test_file_path_rel = result.get("test_file_path", f"tests/test_{item['path'].replace('/', '_')}")

        tests = result.get("tests", [])
        coverage_est = result.get("coverage_estimate", 0)
        edge_cases = result.get("edge_cases_found", [])

        if isinstance(coverage_est, (int, float)):
            combined_coverage += coverage_est

        all_tests.append({
            "file": item["path"],
            "test_file_path": test_file_path_rel,
            "test_code": test_code,
            "tests": tests,
            "coverage_estimate": coverage_est,
            "edge_cases_found": edge_cases,
        })

        if test_code:
            exec_result = await _run_tests(
                repo_path=repo_path.local_path,
                test_code=test_code,
                test_file_path=test_file_path_rel,
                framework=item["framework"],
            )
            combined_execution["passed"] += exec_result.get("passed", 0)
            combined_execution["failed"] += exec_result.get("failed", 0)
            if exec_result.get("coverage") is not None:
                combined_execution["coverage"] = exec_result["coverage"]

        await save_analysis(
            db,
            session_id=session_record.id,
            module=f"testforge:{item['path']}",
            context={"file_path": item["path"], "language": item["language"]},
            prompt=prompt,
            result=result,
            tokens=tokens,
        )

    if file_count == 0:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo generar tests para ningún archivo",
        )

    avg_coverage = round(combined_coverage / file_count, 2)

    summary_result = {
        "files_tested": all_tests,
        "total_files": file_count,
        "coverage_estimate": avg_coverage,
        "execution_result": combined_execution,
    }

    await save_analysis(
        db,
        session_id=session_record.id,
        module="testforge",
        context={
            "github_url": github_url,
            "files_requested": len(files_to_test),
            "chained_from_refactorbot": chained,
        },
        prompt={},
        result=summary_result,
        tokens=total_tokens,
    )

    await update_session_status(db, session_record.id, "done")

    first = all_tests[0] if all_tests else {}
    return TestForgeResponse(
        session_id=session_record.id,
        test_file_path=first.get("test_file_path", ""),
        test_code=first.get("test_code", ""),
        tests=first.get("tests", []),
        coverage_estimate=first.get("coverage_estimate", 0),
        edge_cases_found=first.get("edge_cases_found", []),
        execution_result=combined_execution if combined_execution["passed"] or combined_execution["failed"] else None,
        tokens_used=total_tokens,
        chained_from_refactorbot=chained,
    )


@router.get(
    "/stream/{session_id}",
    summary="Stream de TestForge en tiempo real",
)
async def stream_testforge(
    session_id: uuid.UUID,
    github_url: str,
    file_path: str,
    language: str = "python",
    framework: str = "pytest",
):
    repo_path = await git.clone(github_url)
    code = await git.read_file(repo_path.local_path, file_path)

    return StreamingResponse(
        ai_service.stream_testforge(
            file_path, language, code,
            {"repo": github_url, "framework": framework},
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/session/{session_id}",
    summary="Recupera el análisis de TestForge de una sesión guardada",
)
async def get_testforge_result(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    analysis = await get_session_module_analysis(db, session_id, "testforge")
    if not analysis:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No se encontró análisis de TestForge para esta sesión",
        )

    result = analysis.result or {}
    files_tested = result.get("files_tested", [])
    first = files_tested[0] if files_tested else {}

    return TestForgeResponse(
        session_id=session_id,
        test_file_path=first.get("test_file_path", ""),
        test_code=first.get("test_code", ""),
        tests=first.get("tests", []),
        coverage_estimate=result.get("coverage_estimate", 0),
        edge_cases_found=first.get("edge_cases_found", []),
        execution_result=result.get("execution_result"),
        tokens_used=analysis.tokens_used,
        chained_from_refactorbot=analysis.input_context.get("chained_from_refactorbot", False),
    )


async def _run_tests(
    repo_path: str,
    test_code: str,
    test_file_path: str,
    framework: str = "pytest",
) -> dict:
    result = {"passed": 0, "failed": 0, "coverage": None}

    try:
        abs_test_path = os.path.join(repo_path, test_file_path)
        test_dir = os.path.dirname(abs_test_path)
        os.makedirs(test_dir, exist_ok=True)
        with open(abs_test_path, "w", encoding="utf-8") as f:
            f.write(test_code)
    except Exception as e:
        result["error"] = f"No se pudo escribir test file: {e}"
        return result

    if framework == "pytest":
        try:
            proc = await asyncio.create_subprocess_exec(
                "pytest", abs_test_path, "-q", "--tb=short",
                "--cov", "--cov-report=json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                proc.kill()
                result["error"] = "Timeout ejecutando tests"
                return result

            output = stdout.decode("utf-8", errors="replace")
            _parse_pytest_output(output, result)

            cov_path = os.path.join(repo_path, "coverage.json")
            if os.path.exists(cov_path):
                try:
                    with open(cov_path, "r") as f:
                        cov_data = json.load(f)
                    result["coverage"] = round(cov_data.get("totals", {}).get("percent_covered", 0), 2)
                    os.remove(cov_path)
                except Exception:
                    pass

        except FileNotFoundError:
            result["error"] = "pytest no instalado en el servidor"

    elif framework == "jest":
        try:
            proc = await asyncio.create_subprocess_exec(
                "npx", "jest", abs_test_path, "--coverage", "--silent",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                proc.kill()
                result["error"] = "Timeout ejecutando tests"
                return result

            output = stdout.decode("utf-8", errors="replace")
            _parse_jest_output(output, result)

        except FileNotFoundError:
            result["error"] = "jest/node no instalado en el servidor"

    try:
        os.remove(abs_test_path)
    except Exception:
        pass

    return result


def _parse_pytest_output(output: str, result: dict):
    passed = 0
    failed = 0
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("FAILED"):
            failed += 1
        elif "passed" in line and "failed" not in line:
            import re
            m = re.search(r"(\d+)\s+passed", line)
            if m:
                passed += int(m.group(1))
        elif "failed" in line:
            import re
            m = re.search(r"(\d+)\s+failed", line)
            if m:
                failed += int(m.group(1))
            m2 = re.search(r"(\d+)\s+passed", line)
            if m2:
                passed += int(m2.group(1))
    result["passed"] = passed
    result["failed"] = failed


def _parse_jest_output(output: str, result: dict):
    passed = 0
    failed = 0
    for line in output.splitlines():
        if "Tests:" in line:
            import re
            m = re.search(r"(\d+)\s+passed", line)
            if m:
                passed += int(m.group(1))
            m = re.search(r"(\d+)\s+failed", line)
            if m:
                failed += int(m.group(1))
    result["passed"] = passed
    result["failed"] = failed
