from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_admin_user, get_current_user
from app.models.auth import AuthenticatedUser
from app.models.job import JobSearchResponse, JobStorageStatus
from app.models.skill_intelligence import (
    MarketCollectionRequest,
    MarketCollectionResponse,
    MarketCollectionStatusResponse,
)
from app.services.job_storage_service import search_stored_jsearch_jobs
from app.services.market_collection_service import collect_market_data, get_collection_status

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/jobs", response_model=JobSearchResponse, response_model_exclude_none=True)
def search_market_jobs(
    query: str = Query(min_length=2, max_length=160),
    country: str | None = Query(default=None, min_length=2, max_length=2, pattern="^[A-Za-z]{2}$"),
) -> JobSearchResponse:
    """Read the existing collected job documents. This endpoint never triggers collection."""
    normalized_query = query.strip()
    normalized_country = country.lower() if country else None
    try:
        jobs = search_stored_jsearch_jobs(query=normalized_query, country=normalized_country)
    except Exception:
        return JobSearchResponse(
            status="unavailable", query=normalized_query, country=normalized_country,
            jobs=[], count=0, storage=JobStorageStatus(status="unavailable", stored_count=0),
        )
    fetched_at = max((job.fetched_at for job in jobs), default=None)
    return JobSearchResponse(
        status="available" if jobs else "empty", query=normalized_query,
        country=normalized_country, jobs=jobs, count=len(jobs), fetched_at=fetched_at,
        storage=JobStorageStatus(status="not_attempted", stored_count=0),
    )


@router.post("/admin/collect", response_model=MarketCollectionResponse)
async def trigger_market_collection(
    request: MarketCollectionRequest | None = None,
    current_user: AuthenticatedUser = Depends(get_current_admin_user),
) -> MarketCollectionResponse:
    """Trigger a market collection run for an authenticated Firebase admin."""
    location = request.location if request else None
    country = request.country.lower() if request and request.country else None
    return await collect_market_data(location=location, country=country)


@router.get("/status", response_model=MarketCollectionStatusResponse)
def read_market_collection_status(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> MarketCollectionStatusResponse:
    """Read the latest market collection status and provider metadata."""
    return get_collection_status()


@router.get("/collection/status", response_model=MarketCollectionStatusResponse)
def read_market_collection_status_alias(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> MarketCollectionStatusResponse:
    """Alias for /status endpoint."""
    return get_collection_status()


@router.get("/capabilities")
def read_provider_capabilities():
    """Read the explicit provider historical capability matrix."""
    from app.models.provider_capability import list_provider_capabilities
    return [cap.model_dump(mode="json") for cap in list_provider_capabilities()]
