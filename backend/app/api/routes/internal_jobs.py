from datetime import datetime, timezone
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import _bearer_scheme, get_current_user
from app.core.firebase import get_firestore_client
from app.models.auth import AuthenticatedUser
from app.services.live_job_connectors import PG_CONFIG

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["internal jobs"])


class InternalJobItem(BaseModel):
    id: str
    title: str
    company_name: str
    team: str | None = None
    department: str | None = None
    location: str | None = None
    hiring_manager: str | None = None
    status: str = "Open Internal Requisition"
    urgency: str | None = None
    summary: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    compensation_range: str | None = None
    posted_at: str | None = None
    source: str = "verified_database"


class InternalJobCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    company_id: str | None = Field(default=None, max_length=100)
    team: str | None = Field(default="Engineering", max_length=100)
    department: str | None = Field(default="Technology", max_length=100)
    location: str | None = Field(default="Hybrid / Remote", max_length=200)
    hiring_manager: str | None = Field(default="Internal Talent Acquisition", max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    required_skills: list[str] = Field(default_factory=list)
    status: str = Field(default="Open Internal Requisition", max_length=80)
    urgency: str | None = Field(default="Priority Fill", max_length=80)
    compensation_range: str | None = Field(default=None, max_length=100)


class InternalJobsResponse(BaseModel):
    status: str = "available"
    company_name: str | None = None
    company_id: str | None = None
    count: int = 0
    jobs: list[InternalJobItem] = Field(default_factory=list)


def get_optional_user(
    request: Request,
    credentials = Depends(_bearer_scheme),
) -> AuthenticatedUser | None:
    if not credentials or not credentials.credentials:
        return None
    try:
        return get_current_user(request, credentials)
    except Exception:
        return None


@router.get("/internal", response_model=InternalJobsResponse)
def list_internal_jobs(
    request: Request,
    company_name: str | None = Query(default=None),
    company_id: str | None = Query(default=None),
    role: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    user: AuthenticatedUser | None = Depends(get_optional_user),
) -> InternalJobsResponse:
    """Fetch verified internal job requisitions strictly for the user's company."""
    resolved_company = (company_name or "").strip()
    resolved_company_id = (company_id or "").strip()

    # If company not provided in query params, inspect authenticated user context
    if (not resolved_company or not resolved_company_id) and user:
        try:
            fs = get_firestore_client()
            user_doc = fs.collection("users").document(user.uid).get()
            if user_doc.exists:
                udata = user_doc.to_dict() or {}
                if not resolved_company:
                    resolved_company = str(udata.get("company_name") or udata.get("company") or "").strip()
                if not resolved_company_id:
                    resolved_company_id = str(udata.get("company_id") or "").strip()
        except Exception as exc:
            logger.debug("Failed reading user doc for company context: %s", exc)

        if not resolved_company and resolved_company_id:
            try:
                fs = get_firestore_client()
                comp_doc = fs.collection("companies").document(resolved_company_id).get()
                if comp_doc.exists:
                    cdata = comp_doc.to_dict() or {}
                    resolved_company = str(cdata.get("company_name") or cdata.get("name") or "").strip()
            except Exception as exc:
                logger.debug("Failed reading company doc by ID: %s", exc)

    if not resolved_company and not resolved_company_id:
        return InternalJobsResponse(
            status="empty",
            company_name=None,
            company_id=None,
            count=0,
            jobs=[],
        )

    results: list[InternalJobItem] = []
    seen_titles: set[str] = set()

    # 1. Query Firestore jobs
    try:
        fs = get_firestore_client()
        target_name_lower = resolved_company.lower() if resolved_company else ""
        for doc in fs.collection("jobs").stream():
            d = doc.to_dict() or {}
            doc_comp = str(d.get("company_name") or d.get("company") or "").strip()
            doc_cid = str(d.get("company_id") or "").strip()

            is_match = False
            if resolved_company_id and doc_cid and doc_cid == resolved_company_id:
                is_match = True
            elif target_name_lower and doc_comp:
                doc_comp_lower = doc_comp.lower()
                if (target_name_lower == doc_comp_lower or 
                    target_name_lower in doc_comp_lower or 
                    doc_comp_lower in target_name_lower):
                    is_match = True

            if is_match:
                title = str(d.get("title") or d.get("job_title") or "Open Requisition").strip()
                title_key = title.lower()
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                skills = d.get("skills_raw") or d.get("required_skills") or d.get("skills") or []
                if not isinstance(skills, list):
                    skills = []

                results.append(InternalJobItem(
                    id=doc.id,
                    title=title,
                    company_name=doc_comp or resolved_company,
                    team=str(d.get("team") or d.get("department") or "Engineering"),
                    department=str(d.get("department") or "Technology"),
                    location=str(d.get("location") or "Hybrid / Remote"),
                    hiring_manager=str(d.get("hiring_manager") or d.get("hiringManager") or "Internal Talent Acquisition"),
                    status=str(d.get("status") or "Open Internal Requisition"),
                    urgency=str(d.get("urgency") or "Priority Fill") if d.get("urgency") else None,
                    summary=str(d.get("description") or d.get("summary") or f"Internal role opportunity at {resolved_company}."),
                    required_skills=[str(s) for s in skills if s],
                    compensation_range=str(d.get("compensation") or d.get("compensation_range")) if (d.get("compensation") or d.get("compensation_range")) else None,
                    posted_at=str(d.get("posted_at")) if d.get("posted_at") else None,
                    source="firestore_jobs",
                ))
    except Exception as exc:
        logger.warning("Error querying Firestore jobs for company %s: %s", resolved_company, exc)

    # 2. Query PostgreSQL raw_job_postings
    if len(results) < limit and resolved_company:
        try:
            import psycopg2

            conn = psycopg2.connect(**PG_CONFIG)
            cur = conn.cursor()

            query_sql = """
                SELECT 
                    p.posting_id,
                    p.job_title,
                    p.company_name,
                    COALESCE(p.location_city, 'Bengaluru') AS location_city,
                    p.job_description,
                    p.job_url,
                    p.posted_date
                FROM raw_job_postings p
                WHERE p.company_name ILIKE %s
                ORDER BY p.posted_date DESC NULLS LAST
                LIMIT %s;
            """
            cur.execute(query_sql, (f"%{resolved_company}%", limit - len(results)))
            pg_rows = cur.fetchall()

            posting_ids = [r[0] for r in pg_rows if r[0]]
            skills_by_pid: dict[str, list[str]] = {}
            if posting_ids:
                cur.execute(
                    """
                    SELECT posting_id, array_agg(DISTINCT COALESCE(display_skill, skill_name))
                    FROM raw_skill_observations
                    WHERE posting_id = ANY(%s)
                    GROUP BY posting_id;
                    """,
                    (posting_ids,),
                )
                for pid, s_list in cur.fetchall():
                    skills_by_pid[pid] = [str(s) for s in (s_list or []) if s]

            cur.close()
            conn.close()

            for row in pg_rows:
                pid, p_title, p_comp, p_loc, p_desc, p_url, p_date = row
                p_title_clean = str(p_title or "Engineering Requisition").strip()
                title_key = p_title_clean.lower()
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                skills = skills_by_pid.get(pid, [])
                date_str = p_date.strftime("%Y-%m-%d") if isinstance(p_date, datetime) else str(p_date or "")

                summary_text = (p_desc or f"Core engineering opportunity at {p_comp}. Collaborate with systems and platform teams on mission-critical architecture.").strip()
                if len(summary_text) > 280:
                    summary_text = summary_text[:277] + "…"

                results.append(InternalJobItem(
                    id=f"pg-{pid}",
                    title=p_title_clean,
                    company_name=str(p_comp or resolved_company),
                    team="Engineering & Product Pod",
                    department="Technology",
                    location=f"{p_loc}, India (Hybrid)" if p_loc else "Bangalore, India (Hybrid)",
                    hiring_manager="Internal Talent Acquisition",
                    status="Open Internal Requisition",
                    urgency="Actively Reviewing Internals",
                    summary=summary_text,
                    required_skills=skills if skills else ["Problem Solving", "System Design"],
                    compensation_range=None,
                    posted_at=date_str if date_str else None,
                    source="raw_job_postings",
                ))
        except Exception as exc:
            logger.warning("Error querying PostgreSQL for company %s: %s", resolved_company, exc)

    return InternalJobsResponse(
        status="available" if results else "empty",
        company_name=resolved_company,
        company_id=resolved_company_id or None,
        count=len(results),
        jobs=results[:limit],
    )


@router.post("/internal", response_model=InternalJobItem)
def create_internal_job(
    request: InternalJobCreateRequest,
    user: AuthenticatedUser | None = Depends(get_optional_user),
) -> InternalJobItem:
    """Create a new company internal requisition in the verified database."""
    comp_name = (request.company_name or "").strip()
    comp_id = (request.company_id or "").strip()

    if not comp_name and user:
        try:
            fs = get_firestore_client()
            udoc = fs.collection("users").document(user.uid).get()
            if udoc.exists:
                udata = udoc.to_dict() or {}
                comp_name = str(udata.get("company_name") or "").strip()
                comp_id = str(udata.get("company_id") or "").strip()
        except Exception:
            pass

    if not comp_name:
        comp_name = "Company Internal Requisition"

    job_id = f"req-{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    doc_data = {
        "job_id": job_id,
        "title": request.title,
        "company_name": comp_name,
        "company_id": comp_id or None,
        "team": request.team or "Engineering",
        "department": request.department or "Technology",
        "location": request.location or "Hybrid / Remote",
        "hiring_manager": request.hiring_manager or "Internal Talent Acquisition",
        "description": request.description or f"Internal role opportunity at {comp_name}.",
        "skills_raw": request.required_skills,
        "status": request.status or "Open Internal Requisition",
        "urgency": request.urgency or "Priority Fill",
        "compensation": request.compensation_range,
        "posted_at": now_iso,
        "fetched_at": datetime.now(timezone.utc),
        "source": "company_portal",
    }

    try:
        fs = get_firestore_client()
        fs.collection("jobs").document(job_id).set(doc_data)
    except Exception as exc:
        logger.error("Failed to write internal job to Firestore: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save internal requisition to database.",
        ) from exc

    return InternalJobItem(
        id=job_id,
        title=request.title,
        company_name=comp_name,
        team=request.team,
        department=request.department,
        location=request.location,
        hiring_manager=request.hiring_manager,
        status=request.status or "Open Internal Requisition",
        urgency=request.urgency,
        summary=request.description or f"Internal role opportunity at {comp_name}.",
        required_skills=request.required_skills,
        compensation_range=request.compensation_range,
        posted_at=now_iso,
        source="company_portal",
    )


@router.get("/active")
def get_active_jobs_endpoint(
    query: str = Query(default="Software Engineer", min_length=2, max_length=160),
    country: str | None = Query(default=None, min_length=2, max_length=2, pattern="^[A-Za-z]{2}$"),
):
    from app.api.routes.market import search_market_jobs
    return search_market_jobs(query=query, country=country, live=True)
