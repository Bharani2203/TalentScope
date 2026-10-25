"""Polite collection from configured public ATS job-board JSON APIs."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import hashlib
import json
import logging
import os
from pathlib import Path
import random
import re
import time
from typing import Any, Awaitable, Callable, Iterable
from urllib.parse import quote
import uuid

import httpx

from app.analytics.job_skill_extraction import extract_posting_skills
from app.models.skill_intelligence import MarketObservation, MarketPosting
from app.services.market_data.job_observations import observations_from_postings

logger = logging.getLogger(__name__)

SUPPORTED_ATS = frozenset({"greenhouse", "lever", "ashby", "smartrecruiters"})
PROJECT_USER_AGENT = "TalentScope.ai Public Job Board Collector/1.0"
DEFAULT_BOARD_CONFIG = Path(__file__).resolve().parents[2] / "config" / "public_company_job_boards.json"
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_INDIA_CITIES = frozenset({
    "ahmedabad", "bengaluru", "bangalore", "bhopal", "bhubaneswar", "chandigarh",
    "chennai", "coimbatore", "delhi", "gurugram", "gurgaon", "hyderabad", "indore",
    "jaipur", "kochi", "kolkata", "lucknow", "mumbai", "mysuru", "noida", "pune",
    "surat", "thiruvananthapuram", "vadodara", "visakhapatnam",
})
DEFAULT_SKILL_EXTRACTION_CAP = 60
NON_TECHNICAL_KEYWORDS_ENV = "PUBLIC_JOB_BOARD_NON_TECHNICAL_KEYWORDS"
SKILL_EXTRACTION_CAP_ENV = "PUBLIC_JOB_BOARD_SKILL_EXTRACTION_CAP"
DEFAULT_NON_TECHNICAL_KEYWORDS = (
    "account executive", "business development", "customer success", "customer support",
    "customer service", "human resources", "talent acquisition", "recruiter", "recruiting",
    "sales", "sales representative", "sales manager", "hr", "finance", "accounting",
    "marketing", "legal",
)


@dataclass(frozen=True)
class PublicBoard:
    ats: str
    slug: str

    @classmethod
    def from_mapping(cls, value: Any) -> "PublicBoard":
        if not isinstance(value, dict):
            raise ValueError("Each public job board entry must be an object.")
        ats = str(value.get("ats") or "").strip().casefold()
        slug = str(value.get("slug") or "").strip()
        if ats not in SUPPORTED_ATS:
            raise ValueError("Each board ats must be greenhouse, lever, ashby, or smartrecruiters.")
        if not _SLUG_RE.fullmatch(slug):
            raise ValueError("Each board slug must be a simple ATS board/company identifier.")
        return cls(ats=ats, slug=slug)


@dataclass
class BoardCollectionResult:
    boards_tried: list[str] = field(default_factory=list)
    boards_skipped: list[dict[str, str]] = field(default_factory=list)
    boards_failed: list[dict[str, str]] = field(default_factory=list)
    postings: list[MarketPosting] = field(default_factory=list)
    postings_filtered_by_location: int = 0
    postings_older_than_90_days: int = 0
    postings_date_unknown: int = 0
    postings_without_source_id: int = 0
    postings_missing_title: int = 0
    postings_duplicate_count: int = 0
    postings_stored: int = 0
    persistence_status: str = "not_started"
    postings_remaining_to_store: int = 0
    skill_observations_stored: int = 0
    postings_per_company: dict[str, int] = field(default_factory=dict)
    total_postings: int = 0
    technical_postings: int = 0
    non_technical_postings: int = 0
    non_technical_postings_per_company: dict[str, int] = field(default_factory=dict)
    skill_extraction_cap: int = DEFAULT_SKILL_EXTRACTION_CAP
    skill_extraction_attempted: int = 0
    postings_left_for_next_run: int = 0
    skill_extractions_per_company: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "boards_tried": self.boards_tried,
            "boards_skipped": self.boards_skipped,
            "boards_failed": self.boards_failed,
            "postings_collected": len(self.postings),
            "india_postings_found": len(self.postings),
            "postings_stored": self.postings_stored,
            "persistence_status": self.persistence_status,
            "postings_remaining_to_store": self.postings_remaining_to_store,
            "skill_observations_stored": self.skill_observations_stored,
            "postings_per_company": self.postings_per_company,
            "total_postings": self.total_postings,
            "technical_postings": self.technical_postings,
            "non_technical_postings": self.non_technical_postings,
            "non_technical_postings_per_company": self.non_technical_postings_per_company,
            "skill_extraction_cap": self.skill_extraction_cap,
            "skill_extraction_attempted": self.skill_extraction_attempted,
            "postings_left_for_next_run": self.postings_left_for_next_run,
            "skill_extractions_per_company": self.skill_extractions_per_company,
            "postings_filtered_by_location": self.postings_filtered_by_location,
            "postings_older_than_90_days": self.postings_older_than_90_days,
            "excluded_for_age": self.postings_older_than_90_days,
            "postings_date_unknown": self.postings_date_unknown,
            "excluded_for_unknown_date": self.postings_date_unknown,
            "postings_without_source_id": self.postings_without_source_id,
            "postings_missing_title": self.postings_missing_title,
            "postings_duplicate_count": self.postings_duplicate_count,
        }


class _TextFromHtml(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


def _plain_text(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parser = _TextFromHtml()
    parser.feed(value)
    return " ".join(parser.parts).strip() or None


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _parse_date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            stamp = float(value) / 1000 if abs(float(value)) >= 100_000_000_000 else float(value)
            parsed = datetime.fromtimestamp(stamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            if value.strip().isdigit():
                return _parse_date(int(value.strip()))
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_recent(posted: Any, updated: Any, *, now: datetime) -> tuple[bool, datetime | None]:
    cutoff = now - timedelta(days=90)
    posted_date = _parse_date(posted)
    effective_date = posted_date or _parse_date(updated)
    if effective_date is None:
        return False, None
    return cutoff <= effective_date <= now, effective_date


def _department_text(value: Any) -> str | None:
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, dict):
        return _text(value.get("name") or value.get("label"))
    if isinstance(value, list):
        labels = [_department_text(item) for item in value]
        return ", ".join(label for label in labels if label) or None
    return None


def _non_technical_terms(configured: Iterable[str] | None = None) -> tuple[str, ...]:
    if configured is not None:
        values = configured
    else:
        env_value = os.getenv(NON_TECHNICAL_KEYWORDS_ENV)
        values = env_value.split(",") if env_value else DEFAULT_NON_TECHNICAL_KEYWORDS
    return tuple(dict.fromkeys(str(value).strip().casefold() for value in values if str(value).strip()))


def _is_technical_posting(posting: MarketPosting, terms: Iterable[str]) -> bool:
    text = f"{posting.title or ''} {posting.department or ''}".casefold()
    return not any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


def _skill_extraction_cap(configured: int | None) -> int:
    raw = configured if configured is not None else os.getenv(SKILL_EXTRACTION_CAP_ENV)
    try:
        cap = DEFAULT_SKILL_EXTRACTION_CAP if raw in (None, "") else int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{SKILL_EXTRACTION_CAP_ENV} must be a non-negative integer.") from exc
    if cap < 0:
        raise ValueError("Skill extraction cap must be a non-negative integer.")
    return cap


def _location_text(value: Any) -> tuple[str | None, str | None]:
    if isinstance(value, str):
        return _text(value), None
    if not isinstance(value, dict):
        return None, None
    labels: list[str] = []
    country_code = None
    for key in ("name", "fullLocation", "city", "region", "state", "country", "label", "addressCountry"):
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            labels.append(item.strip())
        elif isinstance(item, dict):
            label = item.get("label") or item.get("name")
            if isinstance(label, str) and label.strip():
                labels.append(label.strip())
            code = item.get("code") or item.get("countryCode")
            if isinstance(code, str):
                country_code = country_code or code.strip()
    for key in ("countryCode", "country_code", "code"):
        code = value.get(key)
        if isinstance(code, str) and len(code.strip()) == 2:
            country_code = code.strip()
    address = value.get("address")
    if isinstance(address, dict):
        for key in ("addressLocality", "addressRegion", "addressCountry"):
            item = address.get(key)
            if isinstance(item, str) and item.strip():
                labels.append(item.strip())
        postal = address.get("postalAddress")
        if isinstance(postal, dict):
            for key in ("addressLocality", "addressRegion", "addressCountry"):
                item = postal.get(key)
                if isinstance(item, str) and item.strip():
                    labels.append(item.strip())
            postal_code = postal.get("countryCode")
            if isinstance(postal_code, str):
                country_code = country_code or postal_code
    return (", ".join(dict.fromkeys(labels)) or None), country_code


def _indicates_india(location: str | None, country_code: str | None = None) -> bool:
    if isinstance(country_code, str) and country_code.strip().casefold() in {"in", "ind"}:
        return True
    normalized = (location or "").casefold()
    if re.search(r"\bindia\b", normalized):
        return True
    return any(re.search(rf"\b{re.escape(city)}\b", normalized) for city in _INDIA_CITIES)


def load_public_boards(path: str | Path = DEFAULT_BOARD_CONFIG) -> list[PublicBoard]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Public job board config could not be read as JSON.") from exc
    entries = payload.get("boards") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        raise ValueError("Public job board config must be a list or an object with a boards list.")
    boards = [PublicBoard.from_mapping(item) for item in entries]
    identities = [(item.ats, item.slug.casefold()) for item in boards]
    if len(identities) != len(set(identities)):
        raise ValueError("Public job board config contains duplicate ats/slug entries.")
    return boards


class PublicCompanyJobBoardCollector:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        request_interval_seconds: float = 1.0,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        if request_interval_seconds < 1.0:
            raise ValueError("Public ATS requests must be at least one second apart.")
        self.transport = transport
        self.request_interval_seconds = request_interval_seconds
        self.sleep = sleep
        self.monotonic = monotonic
        self._last_request_at: float | None = None

    async def collect(
        self,
        boards: Iterable[PublicBoard],
        *,
        now: datetime | None = None,
    ) -> BoardCollectionResult:
        collected_at = now or datetime.now(timezone.utc)
        if collected_at.tzinfo is None:
            collected_at = collected_at.replace(tzinfo=timezone.utc)
        collected_at = collected_at.astimezone(timezone.utc)
        result = BoardCollectionResult()
        seen_posting_ids: set[tuple[str, str]] = set()
        headers = {"User-Agent": PROJECT_USER_AGENT, "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(20), transport=self.transport, headers=headers) as client:
            for board in boards:
                board_id = f"{board.ats}:{board.slug}"
                result.boards_tried.append(board_id)
                try:
                    records, empty = await self._fetch_board(client, board)
                    if empty:
                        result.boards_skipped.append({"ats": board.ats, "slug": board.slug, "reason": "not_found_or_empty"})
                        logger.info("public_job_board_skipped ats=%s reason=not_found_or_empty", board.ats)
                        continue
                    for record in records:
                        posting = self._normalize(board, record, now=collected_at, result=result)
                        if posting is not None:
                            identity = (posting.source.casefold(), str(posting.provider_job_id or posting.posting_id).casefold())
                            if identity in seen_posting_ids:
                                result.postings_duplicate_count += 1
                                continue
                            seen_posting_ids.add(identity)
                            result.postings.append(posting)
                except Exception as exc:
                    result.boards_failed.append({"ats": board.ats, "slug": board.slug, "error_class": type(exc).__name__})
                    logger.warning("public_job_board_failed ats=%s error_class=%s", board.ats, type(exc).__name__)
        counts = Counter(item.company_name or "Unknown" for item in result.postings)
        result.postings_per_company = dict(sorted(counts.items(), key=lambda pair: pair[0].casefold()))
        return result

    async def _get(self, client: httpx.AsyncClient, url: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        if self._last_request_at is not None:
            elapsed = self.monotonic() - self._last_request_at
            wait_for = self.request_interval_seconds - elapsed
            if wait_for > 0:
                await self.sleep(wait_for)
        response = await client.get(url, params=params)
        self._last_request_at = self.monotonic()
        return response

    async def _fetch_board(self, client: httpx.AsyncClient, board: PublicBoard) -> tuple[list[dict[str, Any]], bool]:
        slug = quote(board.slug, safe="._-")
        if board.ats == "greenhouse":
            response = await self._get(client, f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
            if response.status_code == 404:
                return [], True
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("jobs") if isinstance(payload, dict) else None
            return self._rows(rows), not bool(rows)
        if board.ats == "lever":
            response = await self._get(client, f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
            if response.status_code == 404:
                return [], True
            response.raise_for_status()
            return self._rows(response.json()), not bool(response.json())
        if board.ats == "ashby":
            response = await self._get(client, f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            if response.status_code == 404:
                return [], True
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("jobs") if isinstance(payload, dict) else None
            return self._rows(rows), not bool(rows)

        all_rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = await self._get(
                client,
                f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                params={"destination": "PUBLIC", "limit": 100, "offset": offset},
            )
            if response.status_code == 404:
                return [], True
            response.raise_for_status()
            payload = response.json()
            rows = self._rows(payload.get("content") if isinstance(payload, dict) else None)
            all_rows.extend(rows)
            total = payload.get("totalFound") if isinstance(payload, dict) else None
            if not rows or len(rows) < 100 or (isinstance(total, int) and offset + len(rows) >= total):
                break
            offset += len(rows)
        return all_rows, not bool(all_rows)

    @staticmethod
    def _rows(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError("ATS response did not contain a posting list.")
        return [item for item in value if isinstance(item, dict)]

    def _normalize(
        self,
        board: PublicBoard,
        record: dict[str, Any],
        *,
        now: datetime,
        result: BoardCollectionResult,
    ) -> MarketPosting | None:
        if board.ats == "greenhouse":
            source_id = record.get("id")
            title = _text(record.get("title"))
            company = _text((record.get("company") or {}).get("name")) if isinstance(record.get("company"), dict) else None
            location, country_code = _location_text(record.get("location"))
            description = _plain_text(record.get("content"))
            url = _text(record.get("absolute_url"))
            posted = record.get("first_published") or record.get("created_at") or record.get("updated_at")
            updated = record.get("updated_at")
            department = _department_text(record.get("departments"))
        elif board.ats == "lever":
            source_id = record.get("id")
            title = _text(record.get("text"))
            company = _text(record.get("company")) or board.slug
            location, country_code = _location_text((record.get("categories") or {}).get("location") if isinstance(record.get("categories"), dict) else None)
            description = _plain_text(record.get("descriptionPlain") or record.get("description"))
            url = _text(record.get("hostedUrl") or record.get("applyUrl"))
            posted, updated = record.get("createdAt"), record.get("updatedAt")
            categories = record.get("categories") if isinstance(record.get("categories"), dict) else {}
            department = _department_text(categories.get("department") or categories.get("team"))
        elif board.ats == "ashby":
            source_id = record.get("id") or record.get("jobId")
            title = _text(record.get("title"))
            company = _text(record.get("companyName")) or board.slug
            location, country_code = _location_text(record.get("address"))
            location = location or _text(record.get("location"))
            description = _plain_text(record.get("descriptionPlain") or record.get("descriptionHtml"))
            url = _text(record.get("jobUrl") or record.get("applyUrl"))
            posted, updated = record.get("publishedAt"), record.get("updatedAt")
            department = _department_text(record.get("department") or record.get("team"))
        else:
            source_id = record.get("id") or record.get("uuid")
            title = _text(record.get("name"))
            company_value = record.get("company")
            company = _text(company_value.get("name")) if isinstance(company_value, dict) else None
            location, country_code = _location_text(record.get("location"))
            job_ad = record.get("jobAd") if isinstance(record.get("jobAd"), dict) else {}
            sections = job_ad.get("sections") if isinstance(job_ad.get("sections"), dict) else {}
            description_parts = []
            for section in sections.values():
                if isinstance(section, dict) and (text := _plain_text(section.get("text"))):
                    description_parts.append(text)
            description = "\n\n".join(description_parts) or _plain_text(record.get("description"))
            url = _text(record.get("postingUrl") or record.get("applyUrl"))
            posted, updated = record.get("releasedDate"), record.get("updatedOn")
            department = _department_text(record.get("department") or record.get("function"))
        if not source_id and url:
            source_id = "derived:" + hashlib.sha256(url.encode("utf-8")).hexdigest()
        if not source_id:
            result.postings_without_source_id += 1
            return None
        if not title:
            result.postings_missing_title += 1
            return None
        if not location or not _indicates_india(location, country_code):
            result.postings_filtered_by_location += 1
            return None
        recent, valid_date = _is_recent(posted, updated, now=now)
        if valid_date is None:
            result.postings_date_unknown += 1
            return None
        if not recent:
            result.postings_older_than_90_days += 1
            return None
        return MarketPosting(
            source=board.ats,
            posting_id=str(source_id),
            provider_job_id=str(source_id),
            title=title,
            description=description,
            location=location,
            company_name=company or board.slug,
            country="India",
            country_code="in",
            source_url=url,
            posted_at=valid_date.isoformat(),
            updated_at=(_parse_date(updated).isoformat() if _parse_date(updated) else None),
            department=department,
        )


def collect_and_store_public_job_boards(
    config_path: str | Path = DEFAULT_BOARD_CONFIG,
    *,
    collector: PublicCompanyJobBoardCollector | None = None,
    now: datetime | None = None,
    reference_store: Any | None = None,
    posting_persister: Callable[..., int] | None = None,
    observation_persister: Callable[..., int] | None = None,
    dry_run: bool = False,
    skill_extraction_cap: int | None = None,
    non_technical_keywords: Iterable[str] | None = None,
) -> BoardCollectionResult:
    """Collect, extract skills, and persist through existing job/observation stores."""
    collected_at = now or datetime.now(timezone.utc)
    if collected_at.tzinfo is None:
        collected_at = collected_at.replace(tzinfo=timezone.utc)
    collected_at = collected_at.astimezone(timezone.utc)
    boards = load_public_boards(config_path)
    service = collector or PublicCompanyJobBoardCollector()
    result = asyncio.run(service.collect(boards, now=collected_at))
    extraction_cap = _skill_extraction_cap(skill_extraction_cap)
    exclusion_terms = _non_technical_terms(non_technical_keywords)
    result.total_postings = len(result.postings)
    result.skill_extraction_cap = extraction_cap
    technical_postings = [item for item in result.postings if _is_technical_posting(item, exclusion_terms)]
    non_technical_postings = [item for item in result.postings if not _is_technical_posting(item, exclusion_terms)]
    result.technical_postings = len(technical_postings)
    result.non_technical_postings = len(non_technical_postings)
    result.non_technical_postings_per_company = dict(sorted(
        Counter(item.company_name or "Unknown" for item in non_technical_postings).items(),
        key=lambda pair: pair[0].casefold(),
    ))
    result.postings_left_for_next_run = len(technical_postings)
    if dry_run:
        result.persistence_status = "skipped"
        return result
    fetch_run_id = f"public-ats-{uuid.uuid4().hex}"

    # Shuffle with the per-run ID so capped runs don't repeatedly process only
    # the same provider-ordered prefix of a board's results.
    extraction_batch = list(technical_postings)
    random.Random(fetch_run_id).shuffle(extraction_batch)
    extraction_batch = extraction_batch[:extraction_cap]
    result.skill_extraction_attempted = len(extraction_batch)
    result.postings_left_for_next_run = len(technical_postings) - len(extraction_batch)
    result.skill_extractions_per_company = dict(sorted(
        Counter(item.company_name or "Unknown" for item in extraction_batch).items(),
        key=lambda pair: pair[0].casefold(),
    ))
    postings_to_persist = [*non_technical_postings, *extraction_batch]
    for posting in extraction_batch:
        matches = extract_posting_skills({
            "title": posting.title or "",
            "description": posting.description or "",
            "skills_raw": posting.skills,
        }, reference_store=reference_store)
        posting.skills = list(dict.fromkeys(
            str(item.get("normalized_name") or item.get("candidate") or "").strip()
            for item in matches
            if str(item.get("normalized_name") or item.get("candidate") or "").strip()
        ))

    from app.services.job_storage_service import (
        JobStorageResourceExhausted,
        store_collected_market_jobs,
    )
    from app.storage.firestore_observation_store import FirestoreObservationStore

    observations = observations_from_postings(
        result.postings,
        location=None,
        country="in",
        collected_at=collected_at,
        fetch_run_id=fetch_run_id,
        query_id="public-company-job-boards:india:90d",
        panel_version="public-company-job-boards-v1",
    )
    persist_jobs = posting_persister or store_collected_market_jobs
    persist_observations = observation_persister or FirestoreObservationStore().insert_observations
    try:
        result.postings_stored = persist_jobs(
            postings_to_persist, fetched_at=collected_at, fetch_run_id=fetch_run_id,
        ) if postings_to_persist else 0
    except JobStorageResourceExhausted as exc:
        result.postings_stored = exc.completed_count
        result.persistence_status = "resource_exhausted"
        result.postings_remaining_to_store = exc.remaining_count
        logger.warning(
            "Job persistence stopped after a Firestore resource limit: stage=%s stored=%d remaining=%d",
            exc.stage,
            exc.completed_count,
            exc.remaining_count,
        )
        return result
    result.persistence_status = "complete"
    result.skill_observations_stored = persist_observations(observations) if observations else 0
    return result
