from fastapi import APIRouter

from .routes import auth, health, lesson_assets, meta, photo_explain, sign_to_text, speech, text_to_ksl

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(speech.router)
api_router.include_router(text_to_ksl.router)
api_router.include_router(lesson_assets.router)
api_router.include_router(sign_to_text.router)
api_router.include_router(photo_explain.router)
