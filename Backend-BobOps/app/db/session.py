import socket
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings


def _resolve_ipv4(url_str: str) -> str:
    parsed = urlparse(url_str)
    hostname = parsed.hostname
    if hostname:
        try:
            ipv4 = socket.getaddrinfo(hostname, None, socket.AF_INET)[0][4][0]
            url_str = url_str.replace(hostname, ipv4)
        except Exception:
            pass
    return url_str


_db_url = _resolve_ipv4(settings.DATABASE_URL)
engine = create_async_engine(_db_url, echo=settings.DEBUG)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session