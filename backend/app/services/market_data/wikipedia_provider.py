"""Wikipedia technical-interest observation provider based on Wikimedia Pageviews REST API.

Guarantees:
1. Signal type is strictly 'interest' (never 'demand' or 'adoption').
2. Source is strictly 'wikipedia'.
3. History type is strictly 'backfill' for genuine dated API observations.
4. Data origin is strictly 'real' for valid API responses.
5. Incomplete/partial current month is excluded from completed historical observations.
6. Missing periods remain absent; zero interpolation or data fabrication.
7. Strictly isolated series_id: wikipedia:pageviews:{skill_id}:v1.
8. Deterministic observation IDs for idempotent persistence.
"""

from __future__ import annotations

import calendar
import hashlib
import math
import re
from datetime import datetime, timezone
from typing import Any

from app.analytics.skill_registry import SKILLS, SkillDefinition, normalize_skill_entry
from app.models.skill_intelligence import MarketObservation
from app.services.external_apis.wikimedia_pageviews_service import (
    WikimediaError,
    WikimediaPageviewsService,
)

# -----------------------------------------------------------------------------
# Deterministic Article Allowlist
# -----------------------------------------------------------------------------
# Maps canonical_skill_id -> official English Wikipedia article title
WIKIPEDIA_CANONICAL_ARTICLE_ALLOWLIST: dict[str, str] = {
    # 1. Verified test topics required by specification:
    "python": "Python_(programming_language)",
    "react": "React_(software)",
    "cloud_computing": "Cloud_computing",
    # 2. Unambiguous core canonical skills from SKILLS registry:
    "angular": "Angular_(application_platform)",
    "django": "Django_(web_framework)",
    "docker": "Docker_(software)",
    "fastapi": "FastAPI",
    "git": "Git",
    "go": "Go_(programming_language)",
    "javascript": "JavaScript",
    "kubernetes": "Kubernetes",
    "mongodb": "MongoDB",
    "postgresql": "PostgreSQL",
    "redis": "Redis",
    "terraform": "Terraform_(software)",
    "typescript": "TypeScript",
    "vue_js": "Vue.js",
}


def resolve_wikipedia_article_for_skill(skill_identifier: str) -> tuple[SkillDefinition, str]:
    """Resolve a skill input to its canonical definition and verified Wikipedia article title.
    
    Raises:
        ValueError: If the skill is not in the canonical registry or not in the allowlist.
    """
    cleaned = " ".join(skill_identifier.strip().split()).casefold()
    entry = normalize_skill_entry(cleaned)

    definition: SkillDefinition | None = None
    if entry.is_known and entry.canonical_skill_id:
        definition = next((s for s in SKILLS if s.skill_id == entry.canonical_skill_id), None)
    if definition is None:
        definition = next(
            (
                s for s in SKILLS
                if cleaned in {s.skill_id.casefold(), s.name.casefold(), *(a.casefold() for a in s.aliases)}
            ),
            None,
        )

    if definition is None:
        raise ValueError(f"Skill '{skill_identifier}' is not in the canonical skill registry.")

    article = WIKIPEDIA_CANONICAL_ARTICLE_ALLOWLIST.get(definition.skill_id)
    if not article:
        raise ValueError(
            f"Canonical skill '{definition.name}' ({definition.skill_id}) is not mapped in the Wikipedia allowlist."
        )

    return definition, article


def get_completed_month_range(
    start_period: str | None = None,
    end_period: str | None = None,
    *,
    months_back: int = 12,
    now: datetime | None = None,
) -> tuple[str, str, list[str]]:
    """Determine a safe, bounded date range of complete UTC months.
    
    Guarantees:
    - Never includes the current incomplete UTC month.
    - Default range: past `months_back` complete months.
    """
    current_dt = now or datetime.now(timezone.utc)
    current_period = current_dt.strftime("%Y-%m")

    if end_period is not None:
        if end_period >= current_period:
            raise ValueError(
                f"Requested end_period '{end_period}' is not a completed month. "
                f"Historical backfill must end strictly before current UTC month '{current_period}'."
            )
        resolved_end = end_period
    else:
        # Latest complete month = previous month
        curr_year = current_dt.year
        curr_month = current_dt.month
        if curr_month == 1:
            resolved_end = f"{curr_year - 1:04d}-12"
        else:
            resolved_end = f"{curr_year:04d}-{curr_month - 1:02d}"

    if start_period is not None:
        resolved_start = start_period
    else:
        # Calculate start by going back (months_back - 1) months from resolved_end
        end_y, end_m = (int(v) for v in resolved_end.split("-"))
        total_months = end_y * 12 + (end_m - 1) - (months_back - 1)
        start_y = total_months // 12
        start_m = total_months % 12 + 1
        resolved_start = f"{start_y:04d}-{start_m:02d}"

    # Build inclusive monthly list
    s_y, s_m = (int(v) for v in resolved_start.split("-"))
    e_y, e_m = (int(v) for v in resolved_end.split("-"))
    start_idx = s_y * 12 + s_m - 1
    end_idx = e_y * 12 + e_m - 1

    if start_idx > end_idx:
        raise ValueError(f"start_period '{resolved_start}' cannot be after end_period '{resolved_end}'.")

    periods = [f"{idx // 12:04d}-{idx % 12 + 1:02d}" for idx in range(start_idx, end_idx + 1)]
    return resolved_start, resolved_end, periods


class WikipediaPageviewsProvider:
    name = "wikipedia"
    historical_backfill_supported = True
    panel_version = "wikipedia-pageviews-v1"
    extractor_version = "wikimedia-pageviews-monthly-v1"

    def __init__(self, service: WikimediaPageviewsService | None = None):
        self.service = service or WikimediaPageviewsService()

    async def fetch_observations_for_skill(
        self,
        skill_identifier: str,
        start_period: str,
        end_period: str,
        *,
        now: datetime | None = None,
    ) -> list[MarketObservation]:
        """Fetch and convert genuine monthly Wikipedia pageviews into MarketObservation models."""
        current_dt = now or datetime.now(timezone.utc)
        current_period = current_dt.strftime("%Y-%m")

        definition, article = resolve_wikipedia_article_for_skill(skill_identifier)
        items = await self.service.fetch_monthly_pageviews(article, start_period, end_period)

        observations: list[MarketObservation] = []
        for item in items:
            raw_ts = str(item.get("timestamp", ""))
            if not re.fullmatch(r"\d{4}(0[1-9]|1[0-2])0100", raw_ts):
                raise WikimediaError(
                    "Wikimedia returned an invalid monthly pageview timestamp.",
                    category="malformed_data",
                )
            period = f"{raw_ts[:4]}-{raw_ts[4:6]}"

            # Guardrail: exclude partial current month if present in response
            if period >= current_period:
                continue

            raw_views = item["views"]
            if isinstance(raw_views, bool) or not isinstance(raw_views, (int, float)):
                raise WikimediaError(
                    "Wikimedia returned a non-numeric pageview count.",
                    category="malformed_data",
                )
            views = float(raw_views)
            if not math.isfinite(views) or views < 0:
                raise WikimediaError(
                    "Wikimedia returned an invalid pageview count.",
                    category="malformed_data",
                )

            year = int(period[:4])
            month = int(period[5:7])
            last_day = calendar.monthrange(year, month)[1]
            observed_at = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

            record_id = hashlib.sha256(f"wikipedia:{article}:{period}".encode("utf-8")).hexdigest()

            observations.append(
                MarketObservation(
                    id=record_id,
                    source=self.name,
                    skill=definition.name,
                    skill_id=definition.skill_id,
                    location=None,
                    observed_at=observed_at,
                    period=period,
                    scope="global",
                    posting_id=f"article:{article}",
                    signal_type="interest",
                    value=views,
                    unit="pageviews",
                    source_url=self.service.build_url(article, start_period, end_period),
                    metadata={
                        "metric": "wikipedia_monthly_pageviews",
                        "project": item.get("project", "en.wikipedia"),
                        "access": item.get("access", "all-access"),
                        "agent": item.get("agent", "user"),
                        "article": article,
                        "granularity": "monthly",
                    },
                    history_type="backfill",
                    data_origin="real",
                    series_id=f"wikipedia:pageviews:{definition.skill_id}:v1",
                    query_id=(
                        f"wikipedia:pageviews:{definition.skill_id}:"
                        f"{start_period}:{end_period}:v1"
                    ),
                    panel_version=self.panel_version,
                    observation_count=int(views),
                    extractor_version=self.extractor_version,
                    quality={
                        "measure": "Wikimedia pageviews REST API",
                        "agent": "user",
                        "access": "all-access",
                        "verified_article": article,
                    },
                )
            )

        return observations
