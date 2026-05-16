"""
ast_service.py — Wrapper de tree-sitter para DevFlow AI (BobOps2)

Ubicación: app/services/ast_service.py

Responsabilidades:
  - Parsear cualquier archivo de código a AST con tree-sitter
  - Extraer contexto estructural del repo completo
  - Detectar stack tecnológico automáticamente
  - Calcular métricas de complejidad con radon (Python) o heurísticas (JS/TS)
  - Retornar un dict estandarizado que bob_service.py usa como contexto
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Intentar importar dependencias opcionales ──────────────────────────────
try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_typescript as tstypescript
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning("tree-sitter no disponible — usando análisis de texto plano como fallback")

try:
    import radon.complexity as radon_cc
    import radon.metrics as radon_metrics
    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False
    logger.warning("radon no disponible — métricas de complejidad desactivadas")


# ─── Configuración de lenguajes soportados ───────────────────────────────────

SUPPORTED_EXTENSIONS = {
    ".py":   "python",
    ".js":   "javascript",
    ".jsx":  "javascript",
    ".ts":   "typescript",
    ".tsx":  "typescript",
    ".go":   "go",
    ".rb":   "ruby",
    ".java": "java",
    ".rs":   "rust",
    ".cpp":  "cpp",
    ".c":    "c",
}

# Archivos y carpetas que no aportan contexto de código
IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "htmlcov", ".tox",
}

IGNORE_FILES = {
    ".gitignore", ".env", ".env.example", "package-lock.json",
    "yarn.lock", "poetry.lock", "Pipfile.lock", ".DS_Store",
}

# Archivos que definen el stack (orden de prioridad)
STACK_SIGNALS = {
    "package.json":       ("javascript", "Node.js"),
    "next.config.js":     ("javascript", "Next.js"),
    "next.config.ts":     ("typescript", "Next.js"),
    "vite.config.js":     ("javascript", "Vite/React"),
    "angular.json":       ("typescript", "Angular"),
    "nuxt.config.ts":     ("typescript", "Nuxt.js"),
    "pyproject.toml":     ("python",     "Python (pyproject)"),
    "requirements.txt":   ("python",     "Python (pip)"),
    "Pipfile":            ("python",     "Python (pipenv)"),
    "setup.py":           ("python",     "Python (setuptools)"),
    "go.mod":             ("go",         "Go module"),
    "Cargo.toml":         ("rust",       "Rust (cargo)"),
    "pom.xml":            ("java",       "Java (Maven)"),
    "build.gradle":       ("java",       "Java (Gradle)"),
    "Gemfile":            ("ruby",       "Ruby (bundler)"),
    "docker-compose.yml": (None,         "Docker Compose"),
    "Dockerfile":         (None,         "Docker"),
}

MAX_FILE_SIZE_KB = 500   # No parsear archivos mayores a 500 KB
MAX_FILES_TO_PARSE = 200  # Límite para repos muy grandes


# ─── Dataclasses de resultado ────────────────────────────────────────────────

@dataclass
class FunctionInfo:
    name: str
    start_line: int
    end_line: int
    line_count: int
    complexity: int = 0          # Complejidad ciclomática (radon/heurística)
    parameters: list = field(default_factory=list)
    is_async: bool = False
    docstring: Optional[str] = None


@dataclass
class FileInfo:
    path: str                    # Relativo a la raíz del repo
    language: str
    size_kb: float
    line_count: int
    functions: list[FunctionInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    complexity_avg: float = 0.0
    complexity_max: int = 0
    has_tests: bool = False


@dataclass
class RepoContext:
    """Estructura estandarizada que recibe bob_service.py"""
    repo_path: str
    total_files: int
    parsed_files: int
    total_lines: int
    size_kb: float
    languages: dict[str, int]         # {"python": 15, "javascript": 8}
    primary_language: str
    stack: dict[str, str]             # {"backend": "FastAPI", "frontend": "Next.js"}
    framework_signals: list[str]
    entry_points: list[str]
    structure: dict                   # Árbol de directorios
    files: list[dict]                 # Lista de FileInfo como dicts
    complexity_hotspots: list[dict]   # Archivos con mayor deuda técnica
    dependency_graph: dict            # Qué importa qué (simplificado)
    test_coverage_estimate: str       # "none" | "low" | "medium" | "high"


# ─── Servicio principal ──────────────────────────────────────────────────────

class ASTService:
    """
    Parsea un repositorio completo y retorna RepoContext.

    Uso:
        ast_svc = ASTService()
        context = await ast_svc.extract_context("/tmp/my-repo")
        # context es un dict listo para enviar a bob_service.py
    """

    def __init__(self):
        self._parsers: dict[str, "Parser"] = {}
        if TREE_SITTER_AVAILABLE:
            self._init_parsers()

    def _init_parsers(self):
        """Inicializa los parsers de tree-sitter disponibles."""
        try:
            py_lang = Language(tspython.language())
            p = Parser(py_lang)
            self._parsers["python"] = p
        except Exception as e:
            logger.debug("Parser Python no disponible: %s", e)

        try:
            js_lang = Language(tsjavascript.language())
            p = Parser(js_lang)
            self._parsers["javascript"] = p
            self._parsers["jsx"] = p
        except Exception as e:
            logger.debug("Parser JavaScript no disponible: %s", e)

        try:
            ts_lang = Language(tstypescript.language_typescript())
            p = Parser(ts_lang)
            self._parsers["typescript"] = p
            self._parsers["tsx"] = p
        except Exception as e:
            logger.debug("Parser TypeScript no disponible: %s", e)

        logger.info("tree-sitter parsers cargados: %s", list(self._parsers.keys()))

    # ── Método principal ─────────────────────────────────────────────────────

    async def extract_context(self, repo_path: str) -> dict:
        """
        Analiza el repo completo y retorna el contexto como dict.
        Este dict es el que va directo a bob_service.py.

        Args:
            repo_path: ruta absoluta al repo clonado localmente

        Returns:
            dict con toda la información estructural del repo
        """
        root = Path(repo_path)
        if not root.exists():
            raise ASTServiceError(f"El path del repo no existe: {repo_path}")

        logger.info("Iniciando análisis de repo: %s", repo_path)

        # 1. Escanear todos los archivos
        all_files = self._scan_files(root)
        logger.info("Archivos encontrados: %d", len(all_files))

        # 2. Detectar stack
        stack, framework_signals = self._detect_stack(root)

        # 3. Parsear archivos de código (con límite)
        files_to_parse = [f for f in all_files if self._is_code_file(f)][:MAX_FILES_TO_PARSE]
        parsed_files: list[FileInfo] = []

        for file_path in files_to_parse:
            try:
                info = self._parse_file(file_path, root)
                if info:
                    parsed_files.append(info)
            except Exception as e:
                logger.debug("Error parseando %s: %s", file_path, e)

        # 4. Calcular métricas globales
        languages = {} 
        for f in parsed_files: 
            languages[f.language] = languages.get(f.language, 0) + 1

        primary_lang = max(languages, key=languages.get) if languages else "unknown"
        total_lines = sum(f.line_count for f in parsed_files)
        total_size = sum(f.size_kb for f in parsed_files)

        # 5. Hotspots de complejidad
        hotspots = self._find_hotspots(parsed_files)

        # 6. Grafo de dependencias simplificado
        dep_graph = self._build_dependency_graph(parsed_files)

        # 7. Entry points
        entry_points = self._find_entry_points(root, primary_lang)

        # 8. Estructura de directorios
        structure = self._build_structure(root)

        # 9. Estimar cobertura de tests
        test_coverage = self._estimate_test_coverage(all_files, parsed_files)

        context = RepoContext(
            repo_path=str(root),
            total_files=len(all_files),
            parsed_files=len(parsed_files),
            total_lines=total_lines,
            size_kb=round(total_size, 2),
            languages=languages,
            primary_language=primary_lang,
            stack=stack,
            framework_signals=framework_signals,
            entry_points=entry_points,
            structure=structure,
            files=[asdict(f) for f in parsed_files],
            complexity_hotspots=hotspots,
            dependency_graph=dep_graph,
            test_coverage_estimate=test_coverage,
        )

        logger.info(
            "Análisis completado — %d archivos, %d líneas, lenguaje principal: %s",
            len(parsed_files), total_lines, primary_lang,
        )

        return asdict(context)

    # ── Escaneo de archivos ──────────────────────────────────────────────────

    def _scan_files(self, root: Path) -> list[Path]:
        """Retorna todos los archivos del repo, excluyendo los ignorados."""
        files = []
        for path in root.rglob("*"):
            if path.is_file():
                # Ignorar si algún directorio padre está en IGNORE_DIRS
                if any(part in IGNORE_DIRS for part in path.parts):
                    continue
                if path.name in IGNORE_FILES:
                    continue
                files.append(path)
        return files

    def _is_code_file(self, path: Path) -> bool:
        return path.suffix.lower() in SUPPORTED_EXTENSIONS

    # ── Parseo de archivo individual ─────────────────────────────────────────

    def _parse_file(self, file_path: Path, root: Path) -> Optional[FileInfo]:
        """Parsea un archivo y retorna FileInfo. Retorna None si no es parseable."""
        suffix = file_path.suffix.lower()
        language = SUPPORTED_EXTENSIONS.get(suffix)
        if not language:
            return None

        size_kb = file_path.stat().st_size / 1024
        if size_kb > MAX_FILE_SIZE_KB:
            logger.debug("Archivo muy grande, saltando: %s (%.1f KB)", file_path.name, size_kb)
            return None

        try:
            code = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None

        lines = code.splitlines()
        rel_path = str(file_path.relative_to(root))
        has_tests = self._is_test_file(file_path, code)

        # Extraer funciones, clases e imports según el lenguaje
        if language == "python" and TREE_SITTER_AVAILABLE and "python" in self._parsers:
            functions, classes, imports = self._parse_python_ast(code, lines)
        else:
            functions, classes, imports = self._parse_text_fallback(code, language)

        # Calcular complejidad con radon (solo Python)
        complexity_avg, complexity_max = 0.0, 0
        if language == "python" and RADON_AVAILABLE:
            try:
                results = radon_cc.cc_visit(code)
                if results:
                    scores = [r.complexity for r in results]
                    complexity_avg = round(sum(scores) / len(scores), 1)
                    complexity_max = max(scores)
                    # Asignar complejidad individual a cada función
                    cc_by_name = {r.name: r.complexity for r in results}
                    for fn in functions:
                        fn.complexity = cc_by_name.get(fn.name, 0)
            except Exception:
                pass

        return FileInfo(
            path=rel_path,
            language=language,
            size_kb=round(size_kb, 2),
            line_count=len(lines),
            functions=functions,
            imports=imports[:30],    # limitar para no inflar el contexto
            classes=classes,
            complexity_avg=complexity_avg,
            complexity_max=complexity_max,
            has_tests=has_tests,
        )

    # ── Parser Python con tree-sitter ────────────────────────────────────────

    def _parse_python_ast(
        self, code: str, lines: list[str]
    ) -> tuple[list[FunctionInfo], list[str], list[str]]:
        """Extrae funciones, clases e imports de Python usando tree-sitter."""
        parser = self._parsers["python"]
        tree = parser.parse(bytes(code, "utf8"))
        root_node = tree.root_node

        functions, classes, imports = [], [], []

        def walk(node):
            if node.type in ("function_definition", "async_function_definition"):
                is_async = node.type == "async_function_definition"
                name_node = node.child_by_field_name("name")
                params_node = node.child_by_field_name("parameters")
                name = name_node.text.decode() if name_node else "unknown"

                start_line = node.start_point[0] + 1
                end_line   = node.end_point[0] + 1

                # Extraer parámetros
                params = []
                if params_node:
                    for child in params_node.children:
                        if child.type == "identifier":
                            params.append(child.text.decode())

                # Extraer docstring (primer string literal del body)
                docstring = None
                body = node.child_by_field_name("body")
                if body and body.children:
                    first = body.children[0]
                    if first.type == "expression_statement":
                        expr = first.children[0] if first.children else None
                        if expr and expr.type == "string":
                            docstring = expr.text.decode().strip('"\' \n')[:200]

                functions.append(FunctionInfo(
                    name=name,
                    start_line=start_line,
                    end_line=end_line,
                    line_count=end_line - start_line + 1,
                    parameters=params,
                    is_async=is_async,
                    docstring=docstring,
                ))

            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    classes.append(name_node.text.decode())

            elif node.type in ("import_statement", "import_from_statement"):
                imports.append(node.text.decode().strip())

            for child in node.children:
                walk(child)

        walk(root_node)
        return functions, classes, imports

    # ── Fallback de texto plano (para JS/TS y lenguajes sin parser) ──────────

    def _parse_text_fallback(
        self, code: str, language: str
    ) -> tuple[list[FunctionInfo], list[str], list[str]]:
        """
        Análisis heurístico basado en texto cuando tree-sitter no está disponible
        o el lenguaje no tiene parser configurado.
        """
        functions, classes, imports = [], [], []
        lines = code.splitlines()

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Python functions
            if language == "python":
                if stripped.startswith("def ") or stripped.startswith("async def "):
                    name = stripped.split("(")[0].replace("async def ", "").replace("def ", "").strip()
                    functions.append(FunctionInfo(name=name, start_line=i, end_line=i, line_count=1))
                elif stripped.startswith("class "):
                    name = stripped.split("(")[0].split(":")[0].replace("class ", "").strip()
                    classes.append(name)
                elif stripped.startswith("import ") or stripped.startswith("from "):
                    imports.append(stripped[:100])

            # JavaScript / TypeScript functions
            elif language in ("javascript", "typescript"):
                is_fn = (
                    "function " in stripped
                    or stripped.startswith("const ") and "=>" in stripped
                    or stripped.startswith("async ") and ("function" in stripped or "=>" in stripped)
                    or stripped.startswith("export function")
                    or stripped.startswith("export async function")
                    or stripped.startswith("export default function")
                )
                if is_fn:
                    # Extraer nombre de forma heurística
                    parts = stripped.replace("export ", "").replace("default ", "").replace("async ", "")
                    name = parts.split("(")[0].replace("function ", "").replace("const ", "").strip()
                    name = name.split("=")[0].strip() or "anonymous"
                    functions.append(FunctionInfo(name=name, start_line=i, end_line=i, line_count=1))
                elif stripped.startswith("class ") or "class " in stripped and "{" in stripped:
                    name = stripped.split("{")[0].split("extends")[0].replace("class ", "").strip()
                    classes.append(name)
                elif stripped.startswith("import "):
                    imports.append(stripped[:100])

        return functions, classes, imports

    # ── Detección de stack ───────────────────────────────────────────────────

    def _detect_stack(self, root: Path) -> tuple[dict, list[str]]:
        """
        Detecta el stack tecnológico mirando archivos de configuración.
        Retorna (stack_dict, framework_signals).
        """
        stack: dict[str, str] = {}
        signals: list[str] = []

        for filename, (lang, label) in STACK_SIGNALS.items():
            if (root / filename).exists():
                signals.append(label)

                # Inferir capas del stack
                if "Next.js" in label:
                    stack["frontend"] = "Next.js"
                elif "Vite" in label:
                    stack["frontend"] = "React (Vite)"
                elif "Angular" in label:
                    stack["frontend"] = "Angular"
                elif "Nuxt" in label:
                    stack["frontend"] = "Nuxt.js"

                if "FastAPI" in label or ("Python" in label and (root / "main.py").exists()):
                    stack["backend"] = "FastAPI"
                elif "Go module" in label:
                    stack["backend"] = "Go"
                elif "Java (Maven)" in label or "Java (Gradle)" in label:
                    stack["backend"] = "Java"

                if "Docker" in label:
                    stack["infrastructure"] = "Docker"

        # Inferir DB desde requirements.txt o package.json
        req_file = root / "requirements.txt"
        if req_file.exists():
            reqs = req_file.read_text(errors="ignore").lower()
            if "sqlalchemy" in reqs or "asyncpg" in reqs:
                stack["database"] = "PostgreSQL (SQLAlchemy)"
            elif "pymongo" in reqs:
                stack["database"] = "MongoDB"
            elif "redis" in reqs:
                stack.setdefault("cache", "Redis")
            if "fastapi" in reqs:
                stack["backend"] = "FastAPI"

        pkg_file = root / "package.json"
        if pkg_file.exists():
            try:
                pkg = json.loads(pkg_file.read_text(errors="ignore"))
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "next" in deps:
                    stack["frontend"] = "Next.js"
                if "react" in deps and "next" not in deps:
                    stack["frontend"] = "React"
                if "express" in deps:
                    stack.setdefault("backend", "Express")
                if "prisma" in deps or "@prisma/client" in deps:
                    stack.setdefault("database", "PostgreSQL (Prisma)")
                if "mongoose" in deps:
                    stack.setdefault("database", "MongoDB (Mongoose)")
            except Exception:
                pass

        return stack, signals

    # ── Entry points ─────────────────────────────────────────────────────────

    def _find_entry_points(self, root: Path, primary_lang: str) -> list[str]:
        """Detecta los archivos de entrada más comunes según el lenguaje."""
        candidates = {
            "python":     ["main.py", "app.py", "run.py", "server.py", "manage.py", "wsgi.py", "asgi.py"],
            "javascript": ["index.js", "server.js", "app.js", "src/index.js", "pages/index.js"],
            "typescript": ["index.ts", "server.ts", "src/index.ts", "pages/index.tsx", "app/page.tsx"],
            "go":         ["main.go", "cmd/main.go"],
            "java":       ["src/main/java/Main.java", "Application.java"],
        }

        found = []
        for name in candidates.get(primary_lang, []):
            p = root / name
            if p.exists():
                found.append(name)

        return found[:5]

    # ── Estructura de directorios ─────────────────────────────────────────────

    def _build_structure(self, root: Path, max_depth: int = 3) -> dict:
        """
        Construye un árbol de directorios limitado a max_depth.
        Solo incluye directorios y archivos de código relevantes.
        """
        def _recurse(path: Path, depth: int) -> dict | None:
            if depth > max_depth:
                return None
            if path.name in IGNORE_DIRS:
                return None
            if path.is_file():
                if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    return {"type": "file", "language": SUPPORTED_EXTENSIONS[path.suffix.lower()]}
                return None
            children = {}
            try:
                for child in sorted(path.iterdir()):
                    result = _recurse(child, depth + 1)
                    if result is not None:
                        children[child.name] = result
            except PermissionError:
                pass
            return {"type": "dir", "children": children} if children else None

        result = _recurse(root, 0)
        return result.get("children", {}) if result else {}

    # ── Hotspots de complejidad ───────────────────────────────────────────────

    def _find_hotspots(self, parsed_files: list[FileInfo], top_n: int = 10) -> list[dict]:
        """
        Retorna los archivos con mayor deuda técnica para que RefactorBot
        los priorice primero.
        """
        scored = []
        for f in parsed_files:
            score = 0
            score += f.complexity_max * 10          # Penalizar funciones muy complejas
            score += max(0, f.line_count - 300) // 10  # Penalizar archivos muy largos
            long_fns = sum(1 for fn in f.functions if fn.line_count > 50)
            score += long_fns * 15

            if score > 0:
                scored.append({
                    "path":             f.path,
                    "language":         f.language,
                    "debt_score":       score,
                    "complexity_max":   f.complexity_max,
                    "complexity_avg":   f.complexity_avg,
                    "line_count":       f.line_count,
                    "long_functions":   long_fns,
                    "functions_count":  len(f.functions),
                })

        return sorted(scored, key=lambda x: x["debt_score"], reverse=True)[:top_n]

    # ── Grafo de dependencias ─────────────────────────────────────────────────

    def _build_dependency_graph(self, parsed_files: list[FileInfo]) -> dict:
        """
        Grafo simplificado: {archivo: [archivos que importa]}.
        Solo rastrea imports internos (no librerías externas).
        """
        # Mapa de nombres de módulo a path
        module_map: dict[str, str] = {}
        for f in parsed_files:
            stem = Path(f.path).stem
            module_map[stem] = f.path

        graph: dict[str, list[str]] = {}
        for f in parsed_files:
            internal_deps = []
            for imp in f.imports:
                # Extraer nombre del módulo del import
                parts = imp.replace("import ", "").replace("from ", "").split()
                module_name = parts[0].split(".")[0] if parts else ""
                if module_name in module_map and module_map[module_name] != f.path:
                    internal_deps.append(module_map[module_name])
            if internal_deps:
                graph[f.path] = internal_deps

        return graph

    # ── Estimación de cobertura de tests ─────────────────────────────────────

    def _estimate_test_coverage(
        self, all_files: list[Path], parsed_files: list[FileInfo]
    ) -> str:
        """
        Estima el nivel de cobertura de tests mirando cuántos archivos son tests.
        """
        test_files = sum(1 for f in parsed_files if f.has_tests)
        code_files = len(parsed_files) - test_files

        if code_files == 0:
            return "none"

        ratio = test_files / code_files
        if ratio == 0:
            return "none"
        if ratio < 0.2:
            return "low"
        if ratio < 0.5:
            return "medium"
        return "high"

    @staticmethod
    def _is_test_file(path: Path, code: str) -> bool:
        """Detecta si un archivo contiene tests."""
        name = path.name.lower()
        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or name.endswith(".test.js")
            or name.endswith(".test.ts")
            or name.endswith(".spec.js")
            or name.endswith(".spec.ts")
            or "describe(" in code
            or "def test_" in code
        )

    # ── Método de conveniencia para un solo archivo ───────────────────────────

    async def parse_single_file(self, file_path: str, repo_root: str) -> dict:
        """
        Parsea un solo archivo. Útil para RefactorBot y TestForge
        cuando solo necesitan el contexto de un archivo específico.
        """
        path = Path(file_path)
        root = Path(repo_root)
        info = self._parse_file(path, root)
        if not info:
            raise ASTServiceError(f"No se pudo parsear el archivo: {file_path}")
        return asdict(info)


# ─── Excepción personalizada ─────────────────────────────────────────────────

class ASTServiceError(Exception):
    """Se lanza cuando ASTService no puede parsear un archivo o repo."""
    pass


# ─── Instancia singleton ─────────────────────────────────────────────────────
# Uso: from app.services.ast_service import ast_service
ast_service = ASTService()