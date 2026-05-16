SYSTEM_BASE = """Eres un experto en análisis y transformación de código.
Tienes acceso al contexto completo del repositorio.
Debes responder ÚNICAMENTE con JSON puro y válido.
Responde SIEMPRE en español, incluyendo todos los valores de texto dentro del JSON.
Basas tu respuesta ESTRICTAMENTE en el contexto del repositorio proporcionado, sin inventar ni copiar ejemplos.
No uses markdown, ni bloques de código, ni texto adicional antes o después del JSON.
IMPORTANTE: Si tu texto en español contiene comillas dobles dentro de valores JSON (ej: para énfasis como "específicas"), debes ESCAPARLAS usando \\\" para no romper la estructura del JSON."""

PROMPTS = {
    "codelens": """Eres un arquitecto de software senior especializado en onboarding.

A continuación tienes el contexto completo de un repositorio. Genera un **tour de onboarding detallado** en español.

REGLAS ESTRICTAS:
- Responde ÚNICAMENTE con el JSON especificado abajo. Sin markdown, sin bloques de código, sin texto adicional.
- Todos los textos del JSON deben estar en español.
- Cada campo debe ser **concreto, específico y basado exclusivamente** en el contexto real del repositorio.
- Prohibido usar frases genéricas como "arquitectura en capas" o "módulos claramente definidos". Explica CÓMO está organizado, qué tecnologías conecta cada capa y cómo fluyen los datos.
- Los arrays deben contener **al menos 3 elementos** cada uno, salvo que el contexto del repo lo impida objetivamente.
- La respuesta completa debe tener **al menos 600 palabras** de contenido textual.

CONTEXTO DEL REPO:
{repo_context}

ESTRUCTURA EXACTA DEL JSON — Usa estos nombres de campo exactamente:

{{
  "architecture_summary": "Descripción detallada (4-6 oraciones). Incluye: patrón arquitectónico, tecnologías clave, organización de capas/directorios, flujo de datos de alto nivel. Ej: 'Arquitectura hexagonal con dominio en app/models/ y casos de uso en app/services/. FastAPI expone API REST en app/api/v1/ con autenticación JWT. SQLAlchemy como ORM contra PostgreSQL. El frontend en React consume la API mediante hooks personalizados en src/hooks/.'",

  "stack": {{
    "frontend": "Framework y lenguaje real o 'No aplica'",
    "backend": "Framework, lenguaje y runtime reales",
    "database": "Motor de BD y ORM si aplica",
    "infrastructure": "Contenedores, CI/CD, cloud, etc.",
    "testing": "Framework de testing y herramientas de calidad",
    "other": ["tecnología 1", "tecnología 2"]
  }},

  "modules": [
    {{
      "name": "Nombre real del módulo o directorio principal",
      "path": "ruta/relativa/desde/la/raiz",
      "purpose": "Propósito detallado (2-3 oraciones): qué hace exactamente, qué problemas resuelve, con qué otros módulos se comunica y cómo.",
      "complexity": "low|medium|high basado en la complejidad ciclomática y lines_of_code del contexto",
      "dependencies": ["nombre_modulo_del_que_depende"],
      "key_files": [
        {{"path": "ruta/al/archivo.py", "role": "qué rol cumple dentro del módulo (1-2 oraciones)", "lines": 245}}
      ]
    }}
  ],

  "entry_points": [
    {{"path": "src/main.py", "description": "qué inicia y cómo se ejecuta", "type": "application|script|test"}}
  ],

  "key_patterns": [
    {{"pattern": "nombre del patrón (ej: Inyección de Dependencias)", "location": "archivos o módulos donde se usa", "description": "cómo se implementa y por qué es importante para un nuevo desarrollador"}}
  ],

  "learning_path": [
    {{"step": 1, "action": "Comienza por leer archivoX.py que contiene el router principal", "rationale": "por qué este es el primer paso (qué concepto enseña)", "minutes": 15}}
  ],

  "data_flow": {{
    "description": "Descripción del flujo de datos end-to-end: desde que entra un request hasta la respuesta, mencionando archivos clave en cada etapa.",
    "stages": [
      {{"order": 1, "name": "HTTP Request", "files": ["app/api/v1/endpoints/*.py"], "description": "Los requests entran por aquí... qué middlewares procesan..."}}
    ]
  }},

  "test_strategy": {{
    "coverage_estimate": "low|medium|high basado en el contexto",
    "frameworks": ["pytest"],
    "key_test_files": [
      {{"path": "tests/test_x.py", "scope": "qué cubre este archivo"}}
    ],
    "gaps": ["área sin tests que debería tenerlos"]
  }},

  "complexity_hotspots": [
    {{"path": "ruta/al/archivo.py", "debt_score": 245, "risk": "qué riesgo concreto tiene para el proyecto", "recommendation": "acción específica para reducirlo"}}
  ]
}}""",

    "refactorbot": """Analiza el siguiente código e identifica problemas de calidad.

ARCHIVO: {file_path}
LENGUAJE: {language}
CÓDIGO:
{code}

CONTEXTO DEL MÓDULO:
{module_context}

Responde con este JSON exacto (sin markdown, sin texto adicional):
{{
  "debt_score": 0-100,
  "issues": [
    {{
      "type": "long_function|duplicate_code|complex_logic|naming|other",
      "severity": "low|medium|high|critical",
      "line_start": 1,
      "line_end": 50,
      "description": "qué está mal y por qué",
      "suggestion": "cómo arreglarlo",
      "effort": "low|medium|high",
      "impact": "low|medium|high"
    }}
  ],
  "refactored_code": "código completo refactorizado",
  "diff": "unified diff con los cambios realizados",
  "changes_explanation": [
    {{
      "change": "qué cambió",
      "reason": "por qué es mejor así"
    }}
  ],
  "metrics": {{
    "complexity_before": 0,
    "complexity_after": 0,
    "lines_before": 0,
    "lines_after": 0
  }},
  "impact_analysis": {{
    "affected_modules": ["módulo_que_podría_verse_afectado"],
    "breaking_changes": false,
    "migration_notes": "qué verificar antes de aplicar este cambio"
  }}
}}""",

    "testforge": """Genera tests exhaustivos para el siguiente código.

ARCHIVO: {file_path}
LENGUAJE: {language}
FRAMEWORK DE TESTING: {framework}
CÓDIGO A TESTEAR:
{code}

CONTEXTO DEL MÓDULO (dependencias, APIs externas):
{module_context}

Responde con este JSON exacto:
{{
  "test_file_path": "tests/test_{safe_name}.{ext}",
  "test_code": "código completo de tests listo para ejecutar",
  "tests": [
    {{
      "name": "test_nombre_semantico_descripcion",
      "type": "unit|integration|edge_case",
      "what_it_tests": "descripción de qué valida y por qué importa",
      "mocks_needed": ["dependencia_a_mockear"]
    }}
  ],
  "coverage_estimate": 75,
  "setup_instructions": "comandos para instalar dependencias y correr los tests",
  "edge_cases_found": ["caso límite 1", "caso límite 2"]
}}""",

    "docsync": """Detecta qué documentación quedó desactualizada tras estos cambios en el código.

DIFF DE CAMBIOS:
{code_diff}

DOCUMENTACIÓN ACTUAL:
{current_docs}

CONTEXTO DEL REPO:
{repo_context}

Responde con este JSON exacto:
{{
  "outdated_docs": [
    {{
      "file": "README.md",
      "section": "Installation",
      "reason": "el comando de instalación cambió",
      "severity": "low|medium|high"
    }}
  ],
  "updated_docs": [
    {{
      "file": "README.md",
      "content": "contenido completo actualizado del archivo"
    }}
  ],
  "new_docstrings": [
    {{
      "function": "nombre_funcion",
      "file": "ruta/archivo.py",
      "docstring": "docstring completo generado"
    }}
  ],
  "changelog_entry": "- feat: descripción del cambio para el CHANGELOG"
}}""",

    "babeldev": """Migra el siguiente código de {source_lang} a {target_lang}.

CÓDIGO FUENTE ({source_lang}):
{code}

CONTEXTO DEL MÓDULO:
{module_context}

Responde con este JSON exacto:
{{
  "migrated_code": "código completo en {target_lang}",
  "migration_notes": [
    {{
      "original": "patrón en {source_lang}",
      "migrated": "equivalente en {target_lang}",
      "explanation": "por qué se tradujo así"
    }}
  ],
  "no_direct_equivalent": [
    {{
      "feature": "característica sin equivalente directo",
      "workaround": "solución propuesta en {target_lang}"
    }}
  ],
  "migration_plan": [
    {{
      "step": 1,
      "description": "qué migrar primero y por qué",
      "files_affected": ["archivo1", "archivo2"],
      "estimated_effort": "low|medium|high"
    }}
  ],
  "dependencies_map": {{
    "libreria_original": "libreria_equivalente_o_null"
  }}
}}""",
}
