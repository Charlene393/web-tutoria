from fastapi import APIRouter

from .routes import health, photo_explain, sign_to_text, speech, text_to_ksl

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(speech.router)
api_router.include_router(text_to_ksl.router)
api_router.include_router(sign_to_text.router)
api_router.include_router(photo_explain.router)
