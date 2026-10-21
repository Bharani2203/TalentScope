import hashlib
import logging
from datetime import datetime
from pydantic import ValidationError

from google.cloud.firestore_v1 import FieldFilter
from app.core.firebase import get_firestore_client
from app.models.job import Job
from app.models.skill_intelligence import MarketPosting
from app.storage.firestore_read_guard import read_guard

logger = logging.getLogger(__name__)

MAX_JOB_SEARCH_CANDIDATES = 500


def _job_document_id(job_id: str) -> str:
    if "/" not in job_id and job_id not in {".", ".."} and len(job_id.encode("utf-8")) <= 1500:
        return job_id
    return hashlib.sha256(job_id.encode("utf-8")).hexdigest()


def store_jsearch_jobs(jobs: list[Job], *, firestore_client=None) -> int:
    """Upsert normalized provider jobs under jobs/{provider}:{job_id}."""
    identified_by_source_id: dict[tuple[str, str], Job] = {}
    for job in jobs:
        if not job.job_id:
            continue
        identity = (job.source.casefold(), job.job_id)
        prior = identified_by_source_id.get(identity)
        if prior is not None:
            prior_shape = prior.model_dump(mode="json", exclude={"fetched_at", "fetch_run_id"})
            current_shape = job.model_dump(mode="json", exclude={"fetched_at", "fetch_run_id"})
            if prior_shape != current_shape:
                raise ValueError("Conflicting job records share a provider identity.")
            continue
        identified_by_source_id[identity] = job
    identified_jobs = list(identified_by_source_id.values())
    if not identified_jobs:
        return 0

    firestore = firestore_client if firestore_client is not None else get_firestore_client()
    collection = firestore.collection("jobs")
    for offset in range(0, len(identified_jobs), 450):
        batch = firestore.batch()
        for job in identified_jobs[offset:offset + 450]:
            document_id = _job_document_id(f"{job.source}:{job.job_id}")
            # Write the complete normalized shape, including null optional
            # values, so an upsert cannot leave stale fields from an older
            # version of the same provider posting.
            record = job.model_dump(mode="json")
            record["source_job_id"] = job.job_id
            batch.set(collection.document(document_id), record, merge=True)
        batch.commit()

    # A completed batch commit is not sufficient evidence that every canonical
    # posting can be retrieved. Confirm each stable document before reporting
    # the upsert as successful.
    for job in identified_jobs:
        document_id = _job_document_id(f"{job.source}:{job.job_id}")
        snapshot = collection.document(document_id).get()
        stored = snapshot.to_dict() if getattr(snapshot, "exists", False) else None
        expected = job.model_dump(mode="json")
        expected["source_job_id"] = job.job_id
        if not isinstance(stored, dict) or any(stored.get(key) != value for key, value in expected.items()):
            raise RuntimeError("Stored job read-back verification failed.")
    return len(identified_jobs)


def get_jsearch_job(job_id: str, *, firestore_client=None) -> Job | None:
    """Read back a JSearch job from its stable Firestore document."""
    firestore = firestore_client if firestore_client is not None else get_firestore_client()
    snapshot = firestore.collection("jobs").document(_job_document_id(f"jsearch:{job_id}")).get()
    if not snapshot.exists:
        return None
    record = snapshot.to_dict()
    if not isinstance(record, dict):
        return None
    record.pop("source_job_id", None)
    return Job.model_validate(record)


def store_collected_market_jobs(
    postings: list[MarketPosting],
    *,
    fetched_at: datetime,
    fetch_run_id: str | None = None,
    firestore_client=None,
) -> int:
    jobs = [Job(
        # Providers may lack a native ID; adapters then supply a deterministic
        # content-derived posting_id which remains stable for storage/search.
        job_id=posting.provider_job_id or posting.posting_id,
        title=posting.title,
        company_name=posting.company_name,
        location=posting.location,
        country=posting.country,
        country_code=posting.country_code,
        description=posting.description,
        posted_at=posting.posted_at,
        source=posting.source,
        source_url=posting.source_url,
        fetch_run_id=fetch_run_id,
        city=posting.city,
        region=posting.region,
        category=posting.category,
        fetched_at=fetched_at,
    ) for posting in postings if posting.source in {"jsearch", "adzuna"} and (posting.provider_job_id or posting.posting_id)]
    if firestore_client is None:
        return store_jsearch_jobs(jobs)
    return store_jsearch_jobs(jobs, firestore_client=firestore_client)


def search_stored_jsearch_jobs(
    *, query: str, country: str | None = None, limit: int = 100, firestore_client=None,
) -> list[Job]:
    """Search a bounded, recent Firestore job snapshot without contacting providers."""
    normalized = query.casefold().strip()
    result_limit = max(1, min(int(limit), 100))
    candidate_limit = MAX_JOB_SEARCH_CANDIDATES
    normalized_country = country.casefold().strip() if country else None

    firestore = firestore_client if firestore_client is not None else get_firestore_client()
    query_ref = firestore.collection("jobs")
    if normalized_country:
        query_ref = query_ref.where(
            filter=FieldFilter("country_code", "==", normalized_country)
        )
    query_ref = query_ref.order_by("fetched_at", direction="DESCENDING").limit(candidate_limit)
    snapshots = list(query_ref.stream())
    read_guard.record_read("jobs", len(snapshots), query_type="targeted_stored_job_search")

    results: list[Job] = []
    for snapshot in snapshots:
        record = snapshot.to_dict()
        if not isinstance(record, dict):
            continue
        source_job_id = record.pop("source_job_id", None)
        record.setdefault("job_id", source_job_id or snapshot.id)
        haystack = " ".join(str(record.get(field) or "") for field in ("title", "company_name", "description", "location", "category"))
        if normalized and normalized not in haystack.casefold():
            continue
        if country and str(record.get("country_code") or "").casefold() != country.casefold():
            continue
        try:
            results.append(Job.model_validate(record))
        except ValidationError as exc:
            logger.warning("Skipping invalid stored job record (%s)", type(exc).__name__)
            continue
        if len(results) >= result_limit:
            break
    return results
