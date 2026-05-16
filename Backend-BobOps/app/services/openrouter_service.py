"""
openrouter_service.py — OpenRouter implementation of BaseAIService
OpenAI-compatible API, no IAM token needed.
"""

import json
import logging
from typing import AsyncGenerator
import httpx
from app.core.config import settings
from app.services.base_ai_service import BaseAIService, AIServiceError
from app.services.json_utils import repair_json
from app.services.prompts import SYSTEM_BASE, PROMPTS

logger = logging.getLogger(__name__)


class OpenRouterService(BaseAIService):

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        self.model = settings.OPENROUTER_MODEL
        self.timeout = httpx.Timeout(120.0)

    async def _call(
        self,
        system: str,
        user_prompt: str,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> tuple[dict, dict, int]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.0,
        }

        url = f"{self.base_url}/chat/completions"

        for attempt in range(1, max_retries + 1):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    logger.error("OpenRouter API error %s: %s", e.response.status_code, e.response.text)
                    raise AIServiceError(f"OpenRouter API respondió {e.response.status_code}: {e.response.text}") from e
                except httpx.RequestError as e:
                    raise AIServiceError(f"No se pudo conectar con OpenRouter: {e}") from e

            data = response.json()
            raw_text = data["choices"][0]["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens", 0)

            try:
                result = self._parse_json(raw_text)
            except AIServiceError:
                if attempt < max_retries:
                    logger.warning("Intento %d/%d: JSON inválido, reintentando...", attempt, max_retries)
                    continue
                raise

            return payload, result, tokens_used

        raise AIServiceError("No se obtuvo respuesta JSON válida tras %d intentos" % max_retries)

    async def _stream(
        self,
        system: str,
        user_prompt: str,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "stream": True,
        }

        url = f"{self.base_url}/chat/completions"

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

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                r = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return r.status_code == 200
        except Exception as e:
            logger.error("Health check falló: %s", e)
            return False

    @staticmethod
    def _parse_json(raw: str | None) -> dict:
        return repair_json(raw)

    async def analyze_for_codelens(self, repo_context: dict) -> tuple[dict, dict, int]:
        user_prompt = PROMPTS["codelens"].format(
            repo_context=json.dumps(repo_context, indent=2, default=str)
        )
        return await self._call(SYSTEM_BASE, user_prompt)

    async def stream_codelens(self, repo_context: dict) -> AsyncGenerator[str, None]:
        user_prompt = PROMPTS["codelens"].format(
            repo_context=json.dumps(repo_context, indent=2, default=str)
        )
        async for chunk in self._stream(SYSTEM_BASE, user_prompt):
            yield chunk

    async def analyze_for_refactorbot(
        self, file_path: str, language: str, code: str, module_context: dict
    ) -> tuple[dict, dict, int]:
        user_prompt = PROMPTS["refactorbot"].format(
            file_path=file_path,
            language=language,
            code=code,
            module_context=json.dumps(module_context, indent=2, default=str)
        )
        return await self._call(SYSTEM_BASE, user_prompt)

    async def stream_refactorbot(
        self, file_path: str, language: str, code: str, module_context: dict
    ) -> AsyncGenerator[str, None]:
        user_prompt = PROMPTS["refactorbot"].format(
            file_path=file_path,
            language=language,
            code=code,
            module_context=json.dumps(module_context, indent=2, default=str)
        )
        async for chunk in self._stream(SYSTEM_BASE, user_prompt):
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
        return await self._call(SYSTEM_BASE, user_prompt)

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
        async for chunk in self._stream(SYSTEM_BASE, user_prompt):
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
        return await self._call(SYSTEM_BASE, user_prompt)

    async def stream_docsync(
        self, code_diff: str, current_docs: dict, repo_context: dict
    ) -> AsyncGenerator[str, None]:
        user_prompt = PROMPTS["docsync"].format(
            code_diff=code_diff,
            current_docs=json.dumps(current_docs, indent=2, default=str),
            repo_context=json.dumps(repo_context, indent=2, default=str),
        )
        async for chunk in self._stream(SYSTEM_BASE, user_prompt):
            yield chunk
