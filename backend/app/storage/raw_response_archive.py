"""Secret-safe raw response archive with provider-independent persistence."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.storage.raw_archive_backend import (
    FirestoreRawArchiveBackend,
    RawArchiveBackend,
    RawArchiveError,
)

_SENSITIVE_KEY = re.compile(
    r"(?:api.?key|app.?id|app.?key|token|authorization|credential|password|secret|"
    r"header|cookie|private.?key|access.?key|client.?secret)",
    re.IGNORECASE,
)
_SENSITIVE_QUERY_KEY = re.compile(r"^(?:key|api_key|apikey|app_id|app_key|token|access_token|client_secret)$", re.IGNORECASE)
_JSEARCH_FIELDS = {
    "job_id", "job_uid", "job_title", "employer_name", "job_city", "job_state",
    "job_country", "job_location", "job_category", "job_description",
    "job_posted_at_datetime_utc", "job_posted_at", "job_posted_at_timestamp",
    "job_apply_link", "job_google_link", "job_required_skills", "job_employment_type",
}
_ADZUNA_FIELDS = {
    "id", "title", "description", "location", "company", "category",
    "redirect_url", "created", "skills",
}
_GITHUB_FIELDS = {"id", "name", "full_name", "html_url", "language", "created_at", "pushed_at"}
_STACKEXCHANGE_FIELDS = {"question_id", "creation_date", "tags"}


def _safe_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        safe_query = [
            (key, item) for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if not _SENSITIVE_KEY.search(key) and not _SENSITIVE_QUERY_KEY.search(key)
        ]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(safe_query), parts.fragment))
    except Exception:
        return "[unavailable]"


def _safe_value(value: Any, *, key: str | None = None) -> Any:
    if key and _SENSITIVE_KEY.search(key):
        return None
    if isinstance(value, dict):
        return {
            str(child_key): safe
            for child_key, child_value in value.items()
            if (safe := _safe_value(child_value, key=str(child_key))) is not None
        }
    if isinstance(value, list):
        return [safe for child in value if (safe := _safe_value(child)) is not None]
    if isinstance(value, str) and key and (key.endswith("url") or key.endswith("link")):
        return _safe_url(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None


def sanitize_provider_payload(provider: str, payload: Any) -> dict[str, Any]:
    """Keep only response fields used by current normalizers plus safe provider metadata."""
    source = provider.casefold()
    if not isinstance(payload, dict):
        raise ValueError("Provider response must be a JSON object.")
    if source == "jsearch":
        records = payload.get("data")
        if isinstance(records, dict):
            records = records.get("jobs")
        result: dict[str, Any] = {}
        if isinstance(payload.get("status"), str):
            result["status"] = payload["status"]
        if isinstance(records, list):
            result["data"] = [
                _safe_value({key: value for key, value in item.items() if key in _JSEARCH_FIELDS})
                for item in records if isinstance(item, dict)
            ]
        return result
    if source == "adzuna":
        result = {}
        if isinstance(payload.get("count"), (int, float)):
            result["count"] = payload["count"]
        records = payload.get("results")
        if isinstance(records, list):
            result["results"] = [
                _safe_value({key: value for key, value in item.items() if key in _ADZUNA_FIELDS})
                for item in records if isinstance(item, dict)
            ]
        return result
    if source == "github":
        result = {}
        if isinstance(payload.get("total_count"), int) and not isinstance(payload.get("total_count"), bool):
            result["total_count"] = payload["total_count"]
        if isinstance(payload.get("incomplete_results"), bool):
            result["incomplete_results"] = payload["incomplete_results"]
        records = payload.get("items")
        if isinstance(records, list):
            result["items"] = [
                _safe_value({key: value for key, value in item.items() if key in _GITHUB_FIELDS})
                for item in records if isinstance(item, dict)
            ]
        return result
    if source in {"stackexchange", "stack_exchange"}:
        result = {
            key: payload[key]
            for key in ("has_more", "quota_remaining", "quota_max", "backoff")
            if isinstance(payload.get(key), (bool, int))
        }
        records = payload.get("items")
        if isinstance(records, list):
            result["items"] = [
                _safe_value({key: value for key, value in item.items() if key in _STACKEXCHANGE_FIELDS})
                for item in records if isinstance(item, dict)
            ]
        return result
    return _safe_value(payload) or {}


class FirestoreRawResponseArchive:
    """Sanitize and serialize provider payloads before sending bytes to a backend."""

    def __init__(self, backend: RawArchiveBackend | None = None):
        self.backend = backend or FirestoreRawArchiveBackend()

    def archive(
        self,
        *,
        provider: str,
        fetch_run_id: str,
        collected_at: datetime,
        payload: Any,
        content_type: str | None = None,
        response_index: int = 0,
    ) -> dict[str, Any]:
        source = provider.casefold()
        if not re.fullmatch(r"[a-z0-9-]{1,80}", source):
            raise ValueError("Invalid provider name for archive path.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", fetch_run_id):
            raise ValueError("Invalid fetch run identifier for archive path.")
        if collected_at.tzinfo is None:
            collected_at = collected_at.replace(tzinfo=timezone.utc)
        collected_at = collected_at.astimezone(timezone.utc)
        sanitized = sanitize_provider_payload(source, payload)
        body = json.dumps(sanitized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if not isinstance(response_index, int) or isinstance(response_index, bool) or response_index < 0:
            raise ValueError("Invalid response index for archive path.")
        archive_id = f"{source}__{fetch_run_id}__{response_index:06d}"
        path = f"raw_response_archives/{archive_id}"
        candidate_content_type = content_type.split(";", 1)[0].strip() if content_type else "application/json"
        safe_content_type = (
            candidate_content_type
            if re.fullmatch(r"[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+", candidate_content_type)
            else "application/json"
        )
        checksum = hashlib.sha256(body).hexdigest()
        archived_at = datetime.now(timezone.utc)
        chunk_size = getattr(self.backend, "chunk_size", FirestoreRawArchiveBackend.chunk_size)
        chunk_count = max(1, (len(body) + chunk_size - 1) // chunk_size)
        metadata = {
            "archive_id": archive_id,
            "fetch_run_id": fetch_run_id,
            "source": source,
            "provider": source,
            "content_type": safe_content_type,
            "encoding": "utf-8",
            "checksum": checksum,
            "size_bytes": len(body),
            "chunk_count": chunk_count,
            "created_at": archived_at,
            "retention_class": "provider_response",
            "response_index": response_index,
            "collected_at": collected_at.isoformat(),
            "archive_reference": path,
        }
        try:
            self.backend.write_complete(archive_id, metadata, body)
        except RawArchiveError:
            raise
        except Exception:
            raise RuntimeError("Provider response archive could not be stored.") from None
        return {
            "provider": source,
            "fetch_run_id": fetch_run_id,
            "collected_at": collected_at.isoformat(),
            "archived_at": archived_at.isoformat(),
            "archive_reference": path,
            "content_type": safe_content_type,
            "sha256": checksum,
            "size_bytes": len(body),
        }

    def read(self, archive_reference: str) -> dict[str, Any]:
        archive_id = _archive_id_from_reference(archive_reference)
        try:
            metadata, body = self.backend.read_complete(archive_id)
            payload = json.loads(body.decode("utf-8"))
        except RawArchiveError:
            raise
        except Exception:
            raise RuntimeError("Provider response archive could not be read.") from None
        return {
            "metadata": metadata,
            "payload_bytes": body,
            "payload": payload,
            "archive_reference": archive_reference,
        }

    def delete(self, archive_reference: str) -> None:
        archive_id = _archive_id_from_reference(archive_reference)
        try:
            self.backend.delete(archive_id)
        except RawArchiveError:
            raise
        except Exception:
            raise RuntimeError("Provider response archive could not be deleted.") from None


def _archive_id_from_reference(reference: str) -> str:
    prefix = "raw_response_archives/"
    if not isinstance(reference, str) or not reference.startswith(prefix):
        raise ValueError("Invalid raw response archive reference.")
    archive_id = reference[len(prefix):]
    if "/" in archive_id or not re.fullmatch(r"[a-z0-9-]{1,80}__[A-Za-z0-9_-]{1,160}__[0-9]{6,}", archive_id):
        raise ValueError("Invalid raw response archive reference.")
    return archive_id
