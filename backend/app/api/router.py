from fastapi import APIRouter

from app.api.routes import auth as auth_routes, company_relationships, core_intelligence, health, market, onboarding, skills

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_routes.router)
api_router.include_router(onboarding.router)
api_router.include_router(onboarding.role_router)
api_router.include_router(market.router)
api_router.include_router(skills.router)
api_router.include_router(company_relationships.router)
api_router.include_router(core_intelligence.router)
