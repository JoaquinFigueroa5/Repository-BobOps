from abc import ABC, abstractmethod
from typing import AsyncGenerator


class AIServiceError(Exception):
    pass


class BaseAIService(ABC):

    @abstractmethod
    async def analyze_for_codelens(self, repo_context: dict) -> tuple[dict, dict, int]:
        ...

    @abstractmethod
    async def stream_codelens(self, repo_context: dict) -> AsyncGenerator[str, None]:
        ...

    @abstractmethod
    async def analyze_for_refactorbot(
        self, file_path: str, language: str, code: str, module_context: dict
    ) -> tuple[dict, dict, int]:
        ...

    @abstractmethod
    async def stream_refactorbot(
        self, file_path: str, language: str, code: str, module_context: dict
    ) -> AsyncGenerator[str, None]:
        ...

    @abstractmethod
    async def analyze_for_testforge(
        self, file_path: str, language: str, code: str, module_context: dict
    ) -> tuple[dict, dict, int]:
        ...

    @abstractmethod
    async def stream_testforge(
        self, file_path: str, language: str, code: str, module_context: dict
    ) -> AsyncGenerator[str, None]:
        ...

    @abstractmethod
    async def analyze_for_docsync(
        self, code_diff: str, current_docs: dict, repo_context: dict
    ) -> tuple[dict, dict, int]:
        ...

    @abstractmethod
    async def stream_docsync(
        self, code_diff: str, current_docs: dict, repo_context: dict
    ) -> AsyncGenerator[str, None]:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...
