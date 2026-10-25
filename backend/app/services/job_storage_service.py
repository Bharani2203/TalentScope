import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError

from google.api_core.exceptions import ResourceExhausted
from google.cloud.firestore_v1 import FieldFilter
from app.core.firebase import get_firestore_client
from app.models.job import Job
from app.models.skill_intelligence import MarketPosting
from app.storage.firestore_read_guard import read_guard

logger = logging.getLogger(__name__)
STORED_JOB_SCAN_LIMIT = 300
STORED_JOB_SEARCH_PAGE_SIZE = 500
STORED_JOB_SEARCH_MAX_PAGES = 100
JOB_WRITE_BATCH_SIZE = 450

_ROLE_QUERY_WORDS = {
    "developer", "developers", "engineer", "engineers", "analyst", "analysts",
    "scientist", "scientists", "architect", "architects", "manager", "managers",
    "designer", "designers", "specialist", "specialists", "consultant", "consultants",
    "programmer", "programmers", "job", "jobs", "role", "roles", "position", "positions",
}

_CITY_ALIASES = {
    "bangalore": "bengaluru",
    "bengaluru": "bengaluru",
}


def _normalize_city(value: Any) -> str:
    city = re.split(r"[,;|]", str(value or ""), maxsplit=1)[0].strip().casefold()
    return _CITY_ALIASES.get(city, city)


def _job_document_id(job_id: str) -> str:
    if "/" not in job_id and job_id not in {".", ".."} and len(job_id.encode("utf-8")) <= 1500:
        return job_id
    return hashlib.sha256(job_id.encode("utf-8")).hexdigest()


class JobStorageResourceExhausted(RuntimeError):
    def __init__(self, *, completed_count: int, remaining_count: int, stage: str) -> None:
        self.completed_count = completed_count
        self.remaining_count = remaining_count
        self.stage = stage
        super().__init__("Firestore resource limit reached while storing collected jobs.")


def _stored_job_matches(snapshot: Any, expected: dict[str, Any]) -> bool:
    stored = snapshot.to_dict() if getattr(snapshot, "exists", False) else None
    return isinstance(stored, dict) and all(stored.get(key) == value for key, value in expected.items())


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
    all_refs = {}
    expected_by_id = {}
    for job in identified_jobs:
        document_id = _job_document_id(f"{job.source}:{job.job_id}")
        all_refs[document_id] = collection.document(document_id)
        expected_by_id[document_id] = {
            **job.model_dump(mode="json"),
            "source_job_id": job.job_id,
        }
    existing_by_id = {}
    for offset in range(0, len(identified_jobs), JOB_WRITE_BATCH_SIZE):
        jobs_chunk = identified_jobs[offset:offset + JOB_WRITE_BATCH_SIZE]
        refs = [
            all_refs[_job_document_id(f"{job.source}:{job.job_id}")]
            for job in jobs_chunk
        ]
        snapshots = []
        try:
            for snapshot in firestore.get_all(refs):
                snapshots.append(snapshot)
                existing_by_id[snapshot.id] = snapshot
        except ResourceExhausted as exc:
            completed_count = sum(
                1
                for document_id, expected in expected_by_id.items()
                if _stored_job_matches(existing_by_id.get(document_id), expected)
            )
            raise JobStorageResourceExhausted(
                completed_count=completed_count,
                remaining_count=len(identified_jobs) - completed_count,
                stage="dedupe_read",
            ) from exc
        read_guard.record_read("jobs", len(snapshots), query_type="targeted_job_dedupe")

    write_jobs = []
    for job in identified_jobs:
        document_id = _job_document_id(f"{job.source}:{job.job_id}")
        record = expected_by_id[document_id]
        snapshot = existing_by_id.get(document_id)
        if not _stored_job_matches(snapshot, record):
            write_jobs.append((job, document_id, record))

    completed_writes = 0
    for offset in range(0, len(write_jobs), JOB_WRITE_BATCH_SIZE):
        batch_jobs = write_jobs[offset:offset + JOB_WRITE_BATCH_SIZE]
        batch = firestore.batch()
        for _job, document_id, record in batch_jobs:
            batch.set(collection.document(document_id), record, merge=True)
        try:
            batch.commit()
        except ResourceExhausted as exc:
            if completed_writes:
                from app.intelligence_v2.source_registry import invalidate_platform_counts_cache
                invalidate_platform_counts_cache()
            completed_count = len(identified_jobs) - len(write_jobs) + completed_writes
            raise JobStorageResourceExhausted(
                completed_count=completed_count,
                remaining_count=len(identified_jobs) - completed_count,
                stage="write",
            ) from exc
        completed_writes += len(batch_jobs)

    if completed_writes:
        from app.intelligence_v2.source_registry import invalidate_platform_counts_cache
        invalidate_platform_counts_cache()

    if write_jobs:
        for offset in range(0, len(write_jobs), JOB_WRITE_BATCH_SIZE):
            batch_jobs = write_jobs[offset:offset + JOB_WRITE_BATCH_SIZE]
            refs = [collection.document(document_id) for _job, document_id, _record in batch_jobs]
            try:
                snapshots = list(firestore.get_all(refs))
            except ResourceExhausted as exc:
                completed_count = len(identified_jobs) - len(write_jobs) + completed_writes
                raise JobStorageResourceExhausted(
                    completed_count=completed_count,
                    remaining_count=len(identified_jobs) - completed_count,
                    stage="readback",
                ) from exc
            read_guard.record_read("jobs", len(snapshots), query_type="targeted_job_readback")
            snapshots_by_id = {snapshot.id: snapshot for snapshot in snapshots}
            for _job, document_id, expected in batch_jobs:
                snapshot = snapshots_by_id.get(document_id)
                if not _stored_job_matches(snapshot, expected):
                    raise RuntimeError("Stored job read-back verification failed.")
    return len(identified_jobs)


def get_jsearch_job(job_id: str, *, firestore_client=None) -> Job | None:
    """Read back a JSearch job from its stable Firestore document."""
    firestore = firestore_client if firestore_client is not None else get_firestore_client()
    snapshot = firestore.collection("jobs").document(_job_document_id(f"jsearch:{job_id}")).get()
    read_guard.record_read("jobs", 1, query_type="targeted_job_lookup")
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
        updated_at=posting.updated_at,
        source=posting.source,
        source_url=posting.source_url,
        fetch_run_id=fetch_run_id,
        city=posting.city,
        region=posting.region,
        category=posting.category,
        department=posting.department,
        skills_raw=posting.skills,
        fetched_at=fetched_at,
    ) for posting in postings if posting.source in {
        "jsearch", "adzuna", "greenhouse", "lever", "ashby", "smartrecruiters",
    } and (posting.provider_job_id or posting.posting_id)]
    if firestore_client is None:
        return store_jsearch_jobs(jobs)
    return store_jsearch_jobs(jobs, firestore_client=firestore_client)


def search_stored_jsearch_jobs(
    *,
    query: str,
    country: str | None = None,
    location: str | None = None,
    remote: bool = False,
    limit: int = 100,
    firestore_client=None,
) -> list[Job]:
    """Search all stored jobs without contacting providers or triggering collection."""
    return search_stored_jsearch_jobs_with_stats(
        query=query,
        country=country,
        location=location,
        remote=remote,
        limit=limit,
        firestore_client=firestore_client,
    )


class StoredJobSearchResult(list[Job]):
    """List-compatible search result with truthful scan metadata."""

    def __init__(
        self,
        jobs: list[Job],
        scanned_count: int,
        matched_count: int,
        country_filter_applied: str | None = None,
    ) -> None:
        super().__init__(jobs)
        self.scanned_count = scanned_count
        self.matched_count = matched_count
        self.country_filter_applied = country_filter_applied

    @property
    def jobs(self) -> list[Job]:
        """Keep the explicit stats-helper access pattern available."""
        return list(self)


def search_stored_jsearch_jobs_with_stats(
    *,
    query: str,
    country: str | None = None,
    location: str | None = None,
    remote: bool = False,
    limit: int = 100,
    firestore_client=None,
) -> StoredJobSearchResult:
    """Search stored jobs and expose truthful scan/match counts to callers."""
    normalized = query.casefold().strip()
    result_limit = max(1, min(int(limit), 100))
    normalized_country = country.casefold().strip() if country else None
    if normalized_country == "india":
        normalized_country = "in"
    normalized_location = _normalize_city(location) if location else None
    query_terms = [
        item for item in re.findall(r"[a-z0-9+#.]+", normalized)
        if item not in _ROLE_QUERY_WORDS
    ]

    firestore = firestore_client if firestore_client is not None else get_firestore_client()
    query_ref = firestore.collection("jobs")
    if normalized_country:
        query_ref = query_ref.where(
            filter=FieldFilter("country_code", "==", normalized_country)
        )
    query_ref = query_ref.order_by("fetched_at", direction="DESCENDING")
    snapshots = []
    cursor = None
    seen_document_ids: set[str] = set()
    page_count = 0
    while page_count < STORED_JOB_SEARCH_MAX_PAGES:
        page_query = query_ref.limit(STORED_JOB_SEARCH_PAGE_SIZE)
        if cursor is not None:
            page_query = page_query.start_after(cursor)
        page = list(page_query.stream())
        if not page:
            break
        page_count += 1
        new_page = [snapshot for snapshot in page if snapshot.id not in seen_document_ids]
        if not new_page:
            break
        seen_document_ids.update(snapshot.id for snapshot in new_page)
        snapshots.extend(new_page)
        read_guard.record_read("jobs", len(page), query_type="targeted_stored_job_search")
        if len(page) < STORED_JOB_SEARCH_PAGE_SIZE:
            break
        cursor = page[-1]

    # A default India filter is appropriate only when the complete scanned
    # posting collection is explicitly India-only. Unknown country values keep
    # the search unfiltered rather than silently excluding those records.
    if normalized_country is None and snapshots:
        india_only = all(
            str((snapshot.to_dict() or {}).get("country_code") or "").casefold() == "in"
            for snapshot in snapshots
        )
        if india_only:
            normalized_country = "in"

    results: list[Job] = []
    matched_count = 0
    for snapshot in snapshots:
        record = snapshot.to_dict()
        if not isinstance(record, dict):
            continue
        source_job_id = record.pop("source_job_id", None)
        record.setdefault("job_id", source_job_id or snapshot.id)
        searchable_fields = " ".join(
            str(record.get(field) or "") for field in ("title", "description", "company_name")
        )
        extracted_skills = record.get("skills_raw") or []
        if isinstance(extracted_skills, str):
            extracted_skills = [extracted_skills]
        skills_text = " ".join(str(item) for item in extracted_skills)
        searchable = f"{searchable_fields} {skills_text}".casefold()
        phrase_match = bool(normalized and normalized in searchable)
        term_match = any(term in searchable for term in query_terms)
        if normalized and not phrase_match and not term_match:
            continue
        if normalized_country and str(record.get("country_code") or "").casefold() != normalized_country:
            continue
        record_location = record.get("city") or record.get("location")
        if normalized_location and _normalize_city(record_location) != normalized_location:
            continue
        if remote and not re.search(
            r"\bremote\b",
            f"{record.get('title') or ''} {record.get('location') or ''}",
            re.IGNORECASE,
        ):
            continue
        try:
            job = Job.model_validate(record)
        except ValidationError as exc:
            logger.warning("Skipping invalid stored job record (%s)", type(exc).__name__)
            continue
        matched_count += 1
        if len(results) < result_limit:
            results.append(job)
    return StoredJobSearchResult(
        jobs=results,
        scanned_count=len(snapshots),
        matched_count=matched_count,
        country_filter_applied=normalized_country,
    )


def get_recent_posting_sample_stats(*, firestore_client=None, as_of: datetime | None = None) -> dict[tuple[str, str, str, str], dict[str, int]]:
    """Count recent, old, and date-unknown stored postings by provider/run scope/period."""
    from app.storage.firestore_read_guard import read_guard

    firestore = firestore_client if firestore_client is not None else get_firestore_client()
    runs = {
        str((snapshot.to_dict() or {}).get("run_id") or snapshot.id): snapshot.to_dict() or {}
        for snapshot in firestore.collection("fetch_runs").stream()
    }
    read_guard.record_read("fetch_runs", len(runs), query_type="posting_denominator_scope")
    jobs = list(firestore.collection("jobs").stream())
    read_guard.record_read("jobs", len(jobs), query_type="posting_denominator_sample")
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.astimezone(timezone.utc) - timedelta(days=90)
    stats: dict[tuple[str, str, str, str], dict[str, int]] = {}
    for snapshot in jobs:
        record = snapshot.to_dict() or {}
        source = str(record.get("source") or "").casefold()
        run = runs.get(str(record.get("fetch_run_id") or ""), {})
        geography = run.get("geography") if isinstance(run.get("geography"), dict) else {}
        scope = str(geography.get("scope") or ("country" if record.get("country_code") else "global"))
        location = str(
            geography.get("location")
            or _country_name(str(geography.get("country") or record.get("country_code") or ""))
            or ""
        ).strip().casefold()
        fetched_at = record.get("fetched_at")
        if isinstance(fetched_at, str):
            try:
                fetched_at = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            except ValueError:
                fetched_at = None
        if not isinstance(fetched_at, datetime):
            fetched_at = run.get("started_at")
        if not isinstance(fetched_at, datetime):
            continue
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        period = fetched_at.astimezone(timezone.utc).strftime("%Y-%m")
        key = (source, period, scope, location)
        bucket = stats.setdefault(key, {"recent": 0, "older_than_90_days": 0, "date_unknown": 0})
        posted_at = record.get("posted_at")
        parsed_posted = None
        if isinstance(posted_at, datetime):
            parsed_posted = posted_at
        elif isinstance(posted_at, str) and posted_at.strip():
            try:
                parsed_posted = datetime.fromisoformat(posted_at.strip().replace("Z", "+00:00"))
            except ValueError:
                parsed_posted = None
        if parsed_posted is None:
            bucket["date_unknown"] += 1
        else:
            if parsed_posted.tzinfo is None:
                parsed_posted = parsed_posted.replace(tzinfo=timezone.utc)
            if parsed_posted.astimezone(timezone.utc) < cutoff:
                bucket["older_than_90_days"] += 1
            else:
                bucket["recent"] += 1
    return stats


def _country_name(country: str | None) -> str | None:
    if not country:
        return None
    names = {"in": "India", "us": "United States", "gb": "United Kingdom"}
    return names.get(country.casefold(), country.upper())
