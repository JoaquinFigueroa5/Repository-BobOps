"""
bob_service.py — IBM watsonx implementation of BaseAIService
"""

import json
import logging
import time
from typing import AsyncGenerator
import httpx
from app.core.config import settings
from app.services.base_ai_service import BaseAIService, AIServiceError
from app.services.json_utils import repair_json
from app.services.prompts import SYSTEM_BASE, PROMPTS

logger = logging.getLogger(__name__)

# ─── IAM Token URL ───────────────────────────────────────────────────────────
IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"

class BobService(BaseAIService):

    def __init__(self):
        self.base_url   = settings.IBM_BOB_BASE_URL
        self.api_key    = settings.IBM_BOB_API_KEY
        self.project_id = settings.IBM_BOB_PROJECT_ID
        self.timeout    = httpx.Timeout(120.0)

        self._iam_token: str | None = None
        self._iam_token_expires: float = 0.0

    # ── IAM Token — el paso que te faltaba ──────────────────────────────────

    async def _get_iam_token(self) -> str:
        """
        Intercambia el API Key por un Bearer Token de IBM IAM.
        Lo cachea por 50 minutos (expira a los 60).
        """
        now = time.time()
        if self._iam_token and now < self._iam_token_expires:
            return self._iam_token  # usar el token cacheado

        logger.info("Obteniendo nuevo IAM token de IBM Cloud...")
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            try:
                response = await client.post(
                    IAM_TOKEN_URL,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                        "apikey": self.api_key,
                    },
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                    raise AIServiceError(
                    f"No se pudo obtener IAM token: {e.response.status_code} — "
                    "verifica que IBM_BOB_API_KEY sea válido"
                ) from e

        data = response.json()
        self._iam_token = data["access_token"]
        self._iam_token_expires = now + 3000  # 50 minutos de cache
        logger.info("IAM token obtenido exitosamente")
        return self._iam_token

    # ── Método genérico de llamada (corregido) ───────────────────────────────

    async def _call_bob(
        self,
        system: str,
        user_prompt: str,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> tuple[dict, dict, int]:

        token = await self._get_iam_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }

        url = f"{self.base_url}/text/chat?version=2023-05-29"

        payload = {
            "model_id": settings.IBM_BOB_MODEL_ID,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens":  max_tokens,
                "min_new_tokens":  10,
                "temperature":     0.0,
                "repetition_penalty": 1.1,
            },
            "project_id": self.project_id,
        }

        for attempt in range(1, max_retries + 1):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    logger.error("Bob API error %s: %s", e.response.status_code, e.response.text)
                    raise AIServiceError(f"Bob API respondió {e.response.status_code}: {e.response.text}") from e
                except httpx.RequestError as e:
                    raise AIServiceError(f"No se pudo conectar con IBM Bob: {e}") from e

            data = response.json()

            raw_text    = data["choices"][0]["message"]["content"]
            tokens_used = data["usage"].get("generated_tokens", 0)

            try:
                result = self._parse_json(raw_text)
            except AIServiceError:
                if attempt < max_retries:
                    logger.warning("Intento %d/%d: JSON inválido, reintentando...", attempt, max_retries)
                    continue
                raise

            return payload, result, tokens_used

        raise AIServiceError("No se obtuvo respuesta JSON válida tras %d intentos" % max_retries)

    # ── Streaming corregido ──────────────────────────────────────────────────

    async def _stream_bob(
        self,
        system: str,
        user_prompt: str,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:

        token = await self._get_iam_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "Accept":        "text/event-stream",
        }

        payload = {
            "model_id": settings.IBM_BOB_MODEL_ID,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens":  max_tokens,
                "temperature":     0.0,
            },
            "project_id": self.project_id,
            "stream": True,
        }

        url = f"{self.base_url}/text/chat?version=2023-05-29"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and "[DONE]" not in line:
                        try:
                            chunk = json.loads(line[6:])
                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            text = choices[0]["delta"].get("content", "")
                            if text:
                                yield text
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

    # ── health_check corregido ───────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            token = await self._get_iam_token()
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                r = await client.get(
                    f"{self.base_url}/foundation_model_specs?version=2023-05-29",
                    headers={"Authorization": f"Bearer {token}"},
                )
                return r.status_code == 200
        except Exception as e:
            logger.error("Health check falló: %s", e)
            return False

    # ── _parse_json — extrae y repara JSON de la respuesta ──────────────────

    @staticmethod
    def _parse_json(raw: str | None) -> dict:
        return repair_json(raw)

    # ── Métodos públicos por módulo ──────────────────────────────────────────

    async def analyze_for_codelens(self, repo_context: dict) -> tuple[dict, dict, int]:
        user_prompt = PROMPTS["codelens"].format(
            repo_context=json.dumps(repo_context, indent=2, default=str)
        )
        return await self._call_bob(SYSTEM_BASE, user_prompt)

    async def stream_codelens(self, repo_context: dict) -> AsyncGenerator[str, None]:
        user_prompt = PROMPTS["codelens"].format(
            repo_context=json.dumps(repo_context, indent=2, default=str)
        )
        async for chunk in self._stream_bob(SYSTEM_BASE, user_prompt):
            yield chunk

    # ── RefactorBot ──────────────────────────────────────────────────────────

    async def analyze_for_refactorbot(
        self, file_path: str, language: str, code: str, module_context: dict
    ) -> tuple[dict, dict, int]:
        user_prompt = PROMPTS["refactorbot"].format(
            file_path=file_path,
            language=language,
            code=code,
            module_context=json.dumps(module_context, indent=2, default=str)
        )
        return await self._call_bob(SYSTEM_BASE, user_prompt)

    async def stream_refactorbot(
        self, file_path: str, language: str, code: str, module_context: dict
    ) -> AsyncGenerator[str, None]:
        user_prompt = PROMPTS["refactorbot"].format(
            file_path=file_path,
            language=language,
            code=code,
            module_context=json.dumps(module_context, indent=2, default=str)
        )
        async for chunk in self._stream_bob(SYSTEM_BASE, user_prompt):
            yield chunk

    # ── TestForge ──────────────────────────────────────────────────────────

    async def analyze_for_testforge(
        self, file_path: str, language: str, code: str, module_context: dict
    ) -> tuple[dict, dict, int]:
        framework = module_context.get("framework", "pytest")
        user_prompt = PROMPTS["testforge"].format(
            file_path=file_path,
            language=language,
            framework=framework,
            code=code,
            module_context=json.dumps(module_context, indent=2, default=str),
            safe_name=file_path.replace("/", "_").replace(".", "_"),
            ext="py" if "python" in language else "js",
        )
        return await self._call_bob(SYSTEM_BASE, user_prompt)

    async def stream_testforge(
        self, file_path: str, language: str, code: str, module_context: dict
    ) -> AsyncGenerator[str, None]:
        framework = module_context.get("framework", "pytest")
        user_prompt = PROMPTS["testforge"].format(
            file_path=file_path,
            language=language,
            framework=framework,
            code=code,
            module_context=json.dumps(module_context, indent=2, default=str),
            safe_name=file_path.replace("/", "_").replace(".", "_"),
            ext="py" if "python" in language else "js",
        )
        async for chunk in self._stream_bob(SYSTEM_BASE, user_prompt):
            yield chunk

    # ── DocSync ───────────────────────────────────────────────────────────

    async def analyze_for_docsync(
        self, code_diff: str, current_docs: dict, repo_context: dict
    ) -> tuple[dict, dict, int]:
        user_prompt = PROMPTS["docsync"].format(
            code_diff=code_diff,
            current_docs=json.dumps(current_docs, indent=2, default=str),
            repo_context=json.dumps(repo_context, indent=2, default=str),
        )
        return await self._call_bob(SYSTEM_BASE, user_prompt)

    async def stream_docsync(
        self, code_diff: str, current_docs: dict, repo_context: dict
    ) -> AsyncGenerator[str, None]:
        user_prompt = PROMPTS["docsync"].format(
            code_diff=code_diff,
            current_docs=json.dumps(current_docs, indent=2, default=str),
            repo_context=json.dumps(repo_context, indent=2, default=str),
        )
        async for chunk in self._stream_bob(SYSTEM_BASE, user_prompt):
            yield chunk


class BobServiceError(AIServiceError):
    pass