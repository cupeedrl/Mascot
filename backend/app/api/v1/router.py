from fastapi import APIRouter

from app.api.v1.routes import (
    admin,
    ai_vocabulary,
    ai_exercises,
    auth,
    catalog,
    dashboard,
    exercises,
    health,
    review,
    vocabularies,
    vocabulary_library,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["authentication"])
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(ai_vocabulary.router, tags=["AI vocabulary"])
api_router.include_router(ai_exercises.router, tags=["AI exercises"])
api_router.include_router(catalog.router, tags=["catalog"])
api_router.include_router(catalog.catalog_router, tags=["catalog"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(exercises.router, tags=["exercises"])
api_router.include_router(exercises.attempts_router, tags=["exercise attempts"])
api_router.include_router(review.router, tags=["vocabulary review"])
api_router.include_router(vocabularies.router, tags=["vocabulary"])
api_router.include_router(vocabulary_library.router, tags=["vocabulary library"])
