from fastapi import APIRouter
from app.api.v1.endpoints import code_lens, auth, refactorbot, testforge, docsync
# babeldev

api_router = APIRouter()

api_router.include_router(auth.router,         prefix="/auth",       tags=["Auth"])
api_router.include_router(code_lens.router,    prefix="/codelens",   tags=["CodeLens"])
api_router.include_router(refactorbot.router,  prefix="/refactorbot",tags=["RefactorBot"])
api_router.include_router(testforge.router,    prefix="/testforge",  tags=["TestForge"])
api_router.include_router(docsync.router,      prefix="/docsync",    tags=["DocSync"])
# api_router.include_router(babeldev.router,     prefix="/babeldev",   tags=["BabelDev"])