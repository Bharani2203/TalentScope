from fastapi import APIRouter, Request

from app.api.routes import assessments, assistant, auth as auth_routes, career_intelligence, company_relationships, core_intelligence, health, internal_jobs, employee_messages, learning, market, market_intelligence, onboarding, roadmaps, skills, skill_intelligence

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_routes.router)
api_router.include_router(onboarding.router)
api_router.include_router(onboarding.role_router)
api_router.include_router(market.router)
api_router.include_router(skills.router)
api_router.include_router(skill_intelligence.router)
api_router.include_router(company_relationships.router)
api_router.include_router(core_intelligence.router)
api_router.include_router(internal_jobs.router)
api_router.include_router(employee_messages.router)

api_router.include_router(career_intelligence.router)
api_router.include_router(market_intelligence.router)
api_router.include_router(assistant.router)
api_router.include_router(learning.router)
api_router.include_router(assessments.router)
api_router.include_router(roadmaps.router)

career_alias_router = APIRouter(prefix="/career", tags=["career"])

@career_alias_router.get("/jobs")
def get_career_alias_jobs(query: str = "Software Engineer", country: str | None = None):
    from app.api.routes.market import search_market_jobs
    return search_market_jobs(query=query, country=country)

@career_alias_router.post("/recommendations")
def get_career_alias_recommendations_post(request: career_intelligence.RoleRecommendationRequest):
    return career_intelligence.recommend_roles_for_skills(request)

@career_alias_router.get("/recommendations")
def get_career_alias_recommendations_get(
    skills: str | None = None,
    target_role: str | None = None,
    limit: int = 5,
):
    return career_intelligence.get_recommended_roles_get(skills=skills, target_role=target_role, limit=limit)

@career_alias_router.get("/jobs/internal")
def get_career_alias_jobs_internal(
    request: Request,
    company_name: str | None = None,
    company_id: str | None = None,
    role: str | None = None,
    limit: int = 25,
):
    from app.api.routes.internal_jobs import list_internal_jobs
    return list_internal_jobs(request=request, company_name=company_name, company_id=company_id, role=role, limit=limit)

api_router.include_router(career_alias_router)


@api_router.get("/jobs/active")
def get_api_jobs_active(query: str = "Software Engineer", country: str | None = None):
    from app.api.routes.market import search_market_jobs
    return search_market_jobs(query=query, country=country, live=True)

@api_router.get("/intelligence/jobs")
def get_api_intelligence_jobs(query: str = "Software Engineer", country: str | None = None):
    from app.api.routes.market import search_market_jobs
    return search_market_jobs(query=query, country=country, live=True)
