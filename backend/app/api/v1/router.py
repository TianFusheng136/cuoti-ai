from fastapi import APIRouter

from backend.app.api.v1.analysis import router as analysis_router
from backend.app.api.v1.data_management import router as data_management_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.learning import router as learning_router
from backend.app.api.v1.providers import router as providers_router
from backend.app.api.v1.questions import router as questions_router
from backend.app.api.v1.recognition import router as recognition_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(questions_router)
api_router.include_router(providers_router)
api_router.include_router(recognition_router)
api_router.include_router(analysis_router)
api_router.include_router(learning_router)
api_router.include_router(data_management_router)
