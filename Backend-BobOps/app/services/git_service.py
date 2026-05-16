"""
git_service.py — Wrapper de GitPython para DevFlow AI (BobOps2)

Ubicación: app/services/git_service.py

Responsabilidades:
  - Clonar repositorios remotos (GitHub, GitLab, Bitbucket)
  - Gestionar el cache local de repos clonados (no clonar dos veces)
  - Extraer diffs entre commits/branches (para DocSync)
  - Leer archivos individuales del repo (para RefactorBot y TestForge)
  - Limpiar repos del disco cuando ya no se necesitan
  - Retornar metadata del repo (último commit, branches, contribuidores)
"""

import os
import shutil
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

try:
    import git
    from git import Repo, InvalidGitRepositoryError, GitCommandError
    GITPYTHON_AVAILABLE = True
except ImportError:
    GITPYTHON_AVAILABLE = False
    logger.error("GitPython no instalado. Ejecuta: pip install gitpython")


# ─── Configuración ────────────────────────────────────────────────────────────

# Directorio temporal donde se clonan los repos
CLONE_BASE_DIR = Path(os.getenv("CLONE_BASE_DIR", "/tmp/devflow_repos"))
CLONE_BASE_DIR.mkdir(parents=True, exist_ok=True)

# Cuánto tiempo (segundos) mantener un repo en caché antes de re-clonar
CACHE_TTL_SECONDS = int(os.getenv("CLONE_CACHE_TTL", 3600))  # 1 hora por defecto

# Tamaño máximo de repo a clonar (en MB)
MAX_REPO_SIZE_MB = int(os.getenv("MAX_REPO_SIZE_MB", 500))


# ─── Dataclasses de resultado ─────────────────────────────────────────────────

@dataclass
class CommitInfo:
    sha: str
    message: str
    author: str
    date: str
    files_changed: int = 0


@dataclass
class RepoMeta:
    """Metadata del repo que se pasa junto al contexto del AST."""
    url: str
    local_path: str
    name: str                               # ej: "facebook/react"
    default_branch: str
    total_commits: int
    last_commit: Optional[CommitInfo]
    contributors: list[str]
    branches: list[str]
    tags: list[str]
    cloned_at: str
    from_cache: bool


@dataclass
class DiffResult:
    """Resultado de comparar dos commits/branches — usado por DocSync."""
    base_ref: str                           # commit/branch base
    head_ref: str                           # commit/branch nuevo
    files_changed: list[dict] = field(default_factory=list)
    # Cada item: {path, status, diff_text, additions, deletions}
    full_diff: str = ""
    summary: str = ""


# ─── Servicio principal ───────────────────────────────────────────────────────

class GitService:
    """
    Wrapper de GitPython para DevFlow AI.

    Uso básico:
        git_svc = GitService()

        # Clonar un repo
        meta = await git_svc.clone("https://github.com/user/repo")
        local_path = meta.local_path

        # Obtener diff para DocSync
        diff = await git_svc.get_diff(local_path, "HEAD~5", "HEAD")

        # Leer un archivo específico
        code = await git_svc.read_file(local_path, "src/main.py")

        # Limpiar cuando ya no se necesita
        await git_svc.cleanup(local_path)
    """

    def __init__(self):
        if not GITPYTHON_AVAILABLE:
            raise GitServiceError(
                "GitPython no está instalado. "
                "Ejecuta: pip install gitpython"
            )
        self._cache: dict[str, tuple[RepoMeta, datetime]] = {}
        # {url_hash: (RepoMeta, cloned_at)}

    # ── Clonar ───────────────────────────────────────────────────────────────

    async def clone(self, url: str, branch: Optional[str] = None) -> RepoMeta:
        """
        Clona un repositorio remoto o lo retorna desde caché.

        Args:
            url:    URL del repo (https://github.com/user/repo)
            branch: branch específico a clonar (None = default branch)

        Returns:
            RepoMeta con local_path y toda la metadata del repo
        """
        url = url.rstrip("/")
        url_hash = self._url_hash(url)
        local_path = CLONE_BASE_DIR / url_hash

        # Revisar caché en memoria
        if url_hash in self._cache:
            meta, cached_at = self._cache[url_hash]
            age = (datetime.utcnow() - cached_at).total_seconds()
            if age < CACHE_TTL_SECONDS and local_path.exists():
                logger.info("Repo desde caché (%.0f seg): %s", age, url)
                return RepoMeta(**{**asdict(meta), "from_cache": True})

        # Revisar si ya está en disco (entre reinicios del server)
        if local_path.exists():
            try:
                repo = Repo(local_path)
                logger.info("Repo encontrado en disco, actualizando: %s", url)
                repo.remotes.origin.pull()
                meta = self._build_meta(repo, url, local_path, from_cache=True)
                self._cache[url_hash] = (meta, datetime.utcnow())
                return meta
            except Exception as e:
                logger.warning("Repo en disco corrupto, re-clonando: %s", e)
                shutil.rmtree(local_path, ignore_errors=True)

        # Clonar desde cero
        logger.info("Clonando repo: %s → %s", url, local_path)
        try:
            clone_kwargs = {
                "depth": 50,          # shallow clone — suficiente para el análisis
                "no_single_branch": True,  # incluir todas las branches
            }
            if branch:
                clone_kwargs["branch"] = branch

            repo = Repo.clone_from(url, local_path, **clone_kwargs)
            logger.info("Repo clonado exitosamente: %s", url)

        except GitCommandError as e:
            # Limpiar directorio parcial si falló
            shutil.rmtree(local_path, ignore_errors=True)
            if "not found" in str(e).lower() or "repository" in str(e).lower():
                raise GitServiceError(f"Repositorio no encontrado o privado: {url}") from e
            if "already exists" in str(e).lower():
                raise GitServiceError(f"Conflicto de directorio para: {url}") from e
            raise GitServiceError(f"Error al clonar {url}: {e}") from e

        meta = self._build_meta(repo, url, local_path, from_cache=False)
        self._cache[url_hash] = (meta, datetime.utcnow())
        return meta

    # ── Leer archivos ─────────────────────────────────────────────────────────

    async def read_file(self, local_path: str, file_path: str) -> str:
        """
        Lee el contenido de un archivo dentro del repo clonado.

        Args:
            local_path: path local del repo (de RepoMeta.local_path)
            file_path:  path relativo al root del repo ("src/main.py")

        Returns:
            Contenido del archivo como string
        """
        full_path = Path(local_path) / file_path
        if not full_path.exists():
            raise GitServiceError(f"Archivo no encontrado en el repo: {file_path}")
        if not full_path.is_file():
            raise GitServiceError(f"El path no es un archivo: {file_path}")

        try:
            return full_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            raise GitServiceError(f"Error leyendo {file_path}: {e}") from e

    async def list_files(
        self,
        local_path: str,
        extensions: Optional[list[str]] = None,
        exclude_dirs: Optional[list[str]] = None,
    ) -> list[str]:
        """
        Lista todos los archivos del repo, opcionalmente filtrados.

        Args:
            local_path:   path local del repo
            extensions:   filtrar por extensión [".py", ".js"]
            exclude_dirs: directorios a excluir ["node_modules", "__pycache__"]

        Returns:
            Lista de paths relativos al root del repo
        """
        root = Path(local_path)
        _exclude = set(exclude_dirs or [
            "node_modules", "__pycache__", ".git", "venv", ".venv",
            "dist", "build", ".next", "coverage",
        ])

        files = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _exclude for part in path.parts):
                continue
            if extensions and path.suffix.lower() not in extensions:
                continue
            files.append(str(path.relative_to(root)))

        return sorted(files)

    # ── Diffs (para DocSync) ──────────────────────────────────────────────────

    async def get_diff(
        self,
        local_path: str,
        base_ref: str = "HEAD~1",
        head_ref: str = "HEAD",
        max_diff_kb: int = 200,
    ) -> DiffResult:
        """
        Obtiene el diff entre dos refs (commits, branches, tags).
        DocSync usa esto para saber qué cambió y qué docs actualizar.

        Args:
            local_path: path local del repo
            base_ref:   ref base ("HEAD~1", "main", commit SHA)
            head_ref:   ref nuevo ("HEAD", "feature/x", commit SHA)
            max_diff_kb: truncar si el diff es muy grande

        Returns:
            DiffResult con archivos cambiados y el diff completo
        """
        try:
            repo = Repo(local_path)
        except InvalidGitRepositoryError as e:
            raise GitServiceError(f"No es un repo Git válido: {local_path}") from e

        try:
            base_commit = repo.commit(base_ref)
            head_commit = repo.commit(head_ref)
        except Exception as e:
            raise GitServiceError(
                f"No se pudo resolver los refs '{base_ref}' o '{head_ref}': {e}"
            ) from e

        try:
            diffs = base_commit.diff(head_commit, create_patch=True)
        except Exception as e:
            raise GitServiceError(f"Error generando diff: {e}") from e

        files_changed = []
        full_diff_parts = []

        for diff_item in diffs:
            try:
                diff_text = diff_item.diff.decode("utf-8", errors="replace")
            except Exception:
                diff_text = ""

            # Contar adiciones y eliminaciones
            additions = sum(1 for l in diff_text.splitlines() if l.startswith("+") and not l.startswith("+++"))
            deletions = sum(1 for l in diff_text.splitlines() if l.startswith("-") and not l.startswith("---"))

            files_changed.append({
                "path":       diff_item.b_path or diff_item.a_path,
                "status":     self._diff_status(diff_item),
                "additions":  additions,
                "deletions":  deletions,
                "diff_text":  diff_text[:5000],  # limitar por archivo
            })

            full_diff_parts.append(
                f"--- {diff_item.a_path}\n+++ {diff_item.b_path}\n{diff_text}"
            )

        full_diff = "\n".join(full_diff_parts)

        # Truncar si es muy grande
        max_chars = max_diff_kb * 1024
        if len(full_diff) > max_chars:
            full_diff = full_diff[:max_chars] + "\n\n[diff truncado por tamaño]"
            logger.warning("Diff truncado a %d KB", max_diff_kb)

        summary = (
            f"{len(files_changed)} archivos cambiados entre {base_ref} y {head_ref}. "
            f"Total: +{sum(f['additions'] for f in files_changed)} "
            f"-{sum(f['deletions'] for f in files_changed)} líneas."
        )

        return DiffResult(
            base_ref=base_ref,
            head_ref=head_ref,
            files_changed=files_changed,
            full_diff=full_diff,
            summary=summary,
        )

    async def get_latest_diff(self, local_path: str, n_commits: int = 1) -> DiffResult:
        """
        Shortcut: diff de los últimos N commits.
        El más común en DocSync: ver qué cambió en el último commit.
        """
        return await self.get_diff(local_path, f"HEAD~{n_commits}", "HEAD")

    # ── Metadata del repo ─────────────────────────────────────────────────────

    async def get_file_history(
        self, local_path: str, file_path: str, max_commits: int = 10
    ) -> list[CommitInfo]:
        """
        Retorna el historial de commits que tocaron un archivo específico.
        Útil para DocSync: saber cuándo fue modificado por última vez.
        """
        try:
            repo = Repo(local_path)
            commits = list(repo.iter_commits(paths=file_path, max_count=max_commits))
        except Exception as e:
            raise GitServiceError(f"Error obteniendo historial de {file_path}: {e}") from e

        return [
            CommitInfo(
                sha=c.hexsha[:8],
                message=c.message.strip()[:100],
                author=str(c.author),
                date=datetime.fromtimestamp(c.committed_date).isoformat(),
                files_changed=len(c.stats.files),
            )
            for c in commits
        ]

    async def get_current_docs(self, local_path: str) -> dict[str, str]:
        """
        Lee todos los archivos de documentación del repo.
        DocSync los usa como base para detectar qué está desactualizado.

        Returns:
            {path_relativo: contenido} para README, docs/, *.md, docstrings
        """
        docs = {}
        doc_extensions = {".md", ".rst", ".txt", ".adoc"}
        doc_dirs = {"docs", "doc", "documentation", "wiki"}

        root = Path(local_path)
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in {".git", "node_modules", "__pycache__"} for part in path.parts):
                continue

            rel = str(path.relative_to(root))
            is_doc = (
                path.suffix.lower() in doc_extensions
                or any(d in path.parts for d in doc_dirs)
                or path.name.upper() in {"README", "CHANGELOG", "CONTRIBUTING", "LICENSE"}
            )

            if is_doc:
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    docs[rel] = content[:10000]  # limitar a 10KB por archivo
                except Exception:
                    pass

        return docs

    # ── Limpieza ──────────────────────────────────────────────────────────────

    async def cleanup(self, local_path: str) -> bool:
        """
        Elimina un repo del disco.
        Llamar después de que el análisis termine para liberar espacio.
        """
        path = Path(local_path)
        if not path.exists():
            return False
        try:
            shutil.rmtree(path)
            # Limpiar caché en memoria
            url_hash = path.name
            self._cache.pop(url_hash, None)
            logger.info("Repo eliminado: %s", local_path)
            return True
        except Exception as e:
            logger.error("Error eliminando repo %s: %s", local_path, e)
            return False

    async def cleanup_old_repos(self, max_age_seconds: Optional[int] = None) -> int:
        """
        Elimina repos del disco que superaron el TTL de caché.
        Útil para correr periódicamente en producción y liberar espacio.

        Returns:
            Número de repos eliminados
        """
        max_age = max_age_seconds or CACHE_TTL_SECONDS
        now = datetime.utcnow()
        removed = 0

        for url_hash, (meta, cached_at) in list(self._cache.items()):
            age = (now - cached_at).total_seconds()
            if age > max_age:
                path = Path(meta.local_path)
                if path.exists():
                    shutil.rmtree(path, ignore_errors=True)
                del self._cache[url_hash]
                removed += 1
                logger.info("Repo expirado eliminado: %s", meta.url)

        # También revisar directorios en disco que no están en caché
        if CLONE_BASE_DIR.exists():
            for path in CLONE_BASE_DIR.iterdir():
                if path.is_dir() and path.name not in self._cache:
                    try:
                        mtime = datetime.fromtimestamp(path.stat().st_mtime)
                        age = (now - mtime).total_seconds()
                        if age > max_age:
                            shutil.rmtree(path, ignore_errors=True)
                            removed += 1
                    except Exception:
                        pass

        logger.info("Limpieza completada: %d repos eliminados", removed)
        return removed

    # ── Helpers privados ──────────────────────────────────────────────────────

    def _build_meta(
        self, repo: "Repo", url: str, local_path: Path, from_cache: bool
    ) -> RepoMeta:
        """Construye el objeto RepoMeta desde un Repo de GitPython."""
        name = self._extract_repo_name(url)

        # Default branch
        try:
            default_branch = repo.active_branch.name
        except TypeError:
            default_branch = "main"

        # Último commit
        last_commit = None
        try:
            c = repo.head.commit
            last_commit = CommitInfo(
                sha=c.hexsha[:8],
                message=c.message.strip()[:120],
                author=str(c.author),
                date=datetime.fromtimestamp(c.committed_date).isoformat(),
                files_changed=len(c.stats.files),
            )
        except Exception:
            pass

        # Total de commits (puede ser lento en repos grandes, usamos el shallow)
        try:
            total_commits = sum(1 for _ in repo.iter_commits())
        except Exception:
            total_commits = 0

        # Branches disponibles
        try:
            branches = [b.name for b in repo.branches][:20]
        except Exception:
            branches = [default_branch]

        # Tags
        try:
            tags = [t.name for t in repo.tags][:10]
        except Exception:
            tags = []

        # Contribuidores únicos
        try:
            contributors = list({
                str(c.author) for c in repo.iter_commits(max_count=100)
            })[:20]
        except Exception:
            contributors = []

        return RepoMeta(
            url=url,
            local_path=str(local_path),
            name=name,
            default_branch=default_branch,
            total_commits=total_commits,
            last_commit=last_commit,
            contributors=contributors,
            branches=branches,
            tags=tags,
            cloned_at=datetime.utcnow().isoformat(),
            from_cache=from_cache,
        )

    @staticmethod
    def _url_hash(url: str) -> str:
        """Genera un hash único del URL para usar como nombre de directorio."""
        return hashlib.md5(url.encode()).hexdigest()[:16]

    @staticmethod
    def _extract_repo_name(url: str) -> str:
        """Extrae 'owner/repo' de una URL de GitHub/GitLab."""
        url = url.rstrip("/").rstrip(".git")
        parts = url.split("/")
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        return parts[-1]

    @staticmethod
    def _diff_status(diff_item) -> str:
        """Convierte el tipo de diff de GitPython a un string legible."""
        if diff_item.new_file:
            return "added"
        if diff_item.deleted_file:
            return "deleted"
        if diff_item.renamed_file:
            return "renamed"
        return "modified"

    async def health_check(self) -> dict:
        """
        Verifica que git esté disponible en el sistema.
        Útil para el endpoint /health del backend.
        """
        try:
            v = git.cmd.Git().version()
            return {
                "status": "ok",
                "git_version": v,
                "cache_dir": str(CLONE_BASE_DIR),
                "cached_repos": len(self._cache),
                "disk_repos": sum(1 for p in CLONE_BASE_DIR.iterdir() if p.is_dir())
                              if CLONE_BASE_DIR.exists() else 0,
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}


# ─── Excepción personalizada ──────────────────────────────────────────────────

class GitServiceError(Exception):
    """Se lanza cuando GitService no puede completar una operación."""
    pass


# ─── Instancia singleton ──────────────────────────────────────────────────────
# Uso: from app.services.git_service import git_service
git_service = GitService()