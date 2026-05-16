"""
ai_factory.py — Returns the appropriate AI service based on settings.
"""

from app.core.config import settings
from app.services.base_ai_service import BaseAIService, AIServiceError


def create_ai_service() -> BaseAIService:
    provider = settings.AI_PROVIDER.lower()

    if provider == "openrouter":
        from app.services.openrouter_service import OpenRouterService
        return OpenRouterService()

    from app.services.bob_service import BobService
    return BobService()


ai_service = create_ai_service()
