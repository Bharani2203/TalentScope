"""Historical Stack Overflow tag-interest observations.

This provider is invoked only by the explicit backfill command. It is not part of
request handling or the current snapshot collection path.
"""

from __future__ import annotations

import asyncio
import calendar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from app.analytics.skill_registry import SKILLS
from app.models.skill_intelligence import MarketObservation
from app.services.external_apis.stack_exchange_service import StackExchangeError, StackExchangeService


PANEL_VERSION = "stackoverflow-tag-interest-v1"
EXTRACTOR_VERSION = "stackoverflow-question-count-v1"


@dataclass
class HistoricalSeriesResult:
    skill_id: str
    skill: str
    tag: str
    query_id: str
    series_id: str
    observations: list[MarketObservation] = field(default_factory=list)
    periods_found: list[str] = field(default_factory=list)
    periods_with_records: list[str] = field(default_factory=list)
    period_values: dict[str, int] = field(default_factory=dict)
    coverage_gaps: list[str] = field(default_factory=list)
    records_fetched: int = 0
    records_normalized: int = 0
    records_processed: int = 0
    records_rejected: int = 0
    records_filtered: int = 0
    requests_made: int = 0
    quota_remaining: int | None = None
    quota_max: int | None = None
    error_category: str | None = None
    retry_after_seconds: int | None = None


def _month_periods(start_period: str, end_period: str) -> list[str]:
    try:
        start_year, start_month = (int(value) for value in start_period.split("-"))
        end_year, end_month = (int(value) for value in end_period.split("-"))
        if len(start_period) != 7 or len(end_period) != 7 or not (1 <= start_month <= 12 and 1 <= end_month <= 12):
            raise ValueError
        start = start_year * 12 + start_month - 1
        end = end_year * 12 + end_month - 1
        if start > end:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("Periods must be valid inclusive YYYY-MM values with start <= end.") from None
    return [f"{index // 12:04d}-{index % 12 + 1:02d}" for index in range(start, end + 1)]


def _month_bounds(period: str) -> tuple[int, int, datetime]:
    year, month = (int(value) for value in period.split("-"))
    start_dt = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day = calendar.monthrange(year, month)[1]
    end_dt = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    return int(start_dt.timestamp()), int(end_dt.timestamp()), end_dt


def _definition_for_skill(value: str):
    cleaned = " ".join(value.strip().split()).casefold()
    definition = next((item for item in SKILLS if cleaned in {item.name.casefold(), item.skill_id.casefold(), *(alias.casefold() for alias in item.aliases)}), None)
    if definition is None:
        raise ValueError(f"Skill is not in the canonical registry: {value.strip()}.")
    if not definition.stack_exchange_tags:
        raise ValueError(f"Skill has no Stack Exchange tag mapping: {definition.name}.")
    return definition


class StackExchangeHistoricalProvider:
    source = "stackexchange"
    historical_backfill_supported: bool = True

    def __init__(self, service: StackExchangeService | None = None):
        self.service = service or StackExchangeService()

    async def backfill_series(
        self, *, skill: str, start_period: str, end_period: str,
        archive_response: Callable[[Any, str | None], Any] | None = None,
    ) -> list[HistoricalSeriesResult]:
        periods = _month_periods(start_period, end_period)
        definition = _definition_for_skill(skill)
        results: list[HistoricalSeriesResult] = []
        for tag in definition.stack_exchange_tags:
            result = HistoricalSeriesResult(
                skill_id=definition.skill_id,
                skill=definition.name,
                tag=tag,
                query_id=f"stackexchange:stackoverflow:tag:{tag}:v1",
                series_id=f"stackexchange:stackoverflow:question-tag:{tag}:v1",
            )
            for period in periods:
                start_epoch, end_epoch, period_end = _month_bounds(period)
                try:
                    questions = await self._fetch_complete_interval(
                        tag=tag,
                        start_epoch=start_epoch,
                        end_epoch=end_epoch,
                        result=result,
                        archive_response=archive_response,
                    )
                except StackExchangeError as error:
                    result.coverage_gaps.append(period)
                    result.error_category = error.category
                    result.retry_after_seconds = error.backoff
                    # A quota/backoff response applies to subsequent periods too.
                    if error.category == "rate_limit":
                        result.coverage_gaps.extend(item for item in periods if item > period)
                        break
                    continue

                valid_questions = [item for item in questions.values() if isinstance(item.get("question_id"), int)]
                timestamps = [item["creation_date"] for item in valid_questions]
                observed_at = period_end
                result.observations.append(MarketObservation(
                    source=self.source,
                    skill=definition.name,
                    skill_id=definition.skill_id,
                    signal_type="interest",
                    observed_at=observed_at,
                    period=period,
                    location=None,
                    scope="global",
                    posting_id=f"monthly-count:{tag}:{period}",
                    value=float(len(valid_questions)),
                    unit="questions",
                    source_url=self.service.endpoint,
                    metadata={
                        "api_endpoint": self.service.endpoint,
                        "site": "stackoverflow",
                        "tag": tag,
                        "metric": "questions_created_with_tag_in_period",
                        "created_at_field": "creation_date",
                        "period_timezone": "UTC",
                        "source_record_count": len(valid_questions),
                        "source_created_at_min": min(timestamps) if timestamps else None,
                        "source_created_at_max": max(timestamps) if timestamps else None,
                    },
                    history_type="backfill",
                    data_origin="real",
                    series_id=result.series_id,
                    query_id=result.query_id,
                    panel_version=PANEL_VERSION,
                    denominator=None,
                    quality={
                        "coverage": "complete",
                        "pagination_complete": True,
                        "source_reported_zero": len(valid_questions) == 0,
                    },
                    confidence=None,
                    observation_count=len(valid_questions),
                    extractor_version=EXTRACTOR_VERSION,
                    annotations=[{
                        "aggregation": "count of unique returned Stack Overflow questions by creation_date",
                        "date_interval": "inclusive month in UTC",
                        "observed_at_semantics": "calendar period end anchor",
                    }],
                ))
                result.periods_found.append(period)
                result.period_values[period] = len(valid_questions)
                if valid_questions:
                    result.periods_with_records.append(period)
                result.records_processed += len(valid_questions)
            results.append(result)
        return results

    async def _fetch_complete_interval(
        self,
        *,
        tag: str,
        start_epoch: int,
        end_epoch: int,
        result: HistoricalSeriesResult,
        archive_response: Callable[[Any, str | None], Any] | None = None,
    ) -> dict[int, dict[str, Any]]:
        """Enumerate an inclusive Unix-second interval, splitting at API page cap."""
        rejected_before = result.records_rejected
        filtered_before = result.records_filtered
        interval_records: dict[int, dict[str, Any]] = {}
        has_more = False
        for page_number in range(1, self.service.anonymous_page_limit + 1):
            page_args = {"tag": tag, "fromdate": start_epoch, "todate": end_epoch, "page": page_number}
            if archive_response is not None:
                page_args["raw_response_callback"] = archive_response
            page = await self.service.questions_page(**page_args)
            result.requests_made += 1
            result.records_fetched += len(page.items)
            result.quota_remaining = page.quota_remaining
            result.quota_max = page.quota_max
            rejected_on_page = 0
            for item in page.items:
                if not isinstance(item, dict):
                    rejected_on_page += 1
                    continue
                question_id = item.get("question_id")
                created_at = item.get("creation_date")
                tags = item.get("tags")
                if (
                    not isinstance(question_id, int)
                    or not isinstance(created_at, int)
                    or not isinstance(tags, list)
                ):
                    rejected_on_page += 1
                    continue
                if tag not in tags or not start_epoch <= created_at <= end_epoch:
                    result.records_filtered += 1
                    continue
                interval_records[question_id] = {
                    "question_id": question_id,
                    "creation_date": created_at,
                }
            result.records_rejected += rejected_on_page
            result.records_normalized += len(page.items) - rejected_on_page
            has_more = page.has_more
            if page.quota_remaining is not None and page.quota_remaining <= 0 and has_more:
                raise StackExchangeError("Stack Exchange quota is exhausted.", category="rate_limit")
            if page.backoff and has_more:
                if page.backoff > 30:
                    raise StackExchangeError("Stack Exchange requested a long backoff.", category="rate_limit", backoff=page.backoff)
                await asyncio.sleep(page.backoff)
            if not page.has_more:
                if result.records_rejected > rejected_before or result.records_filtered > filtered_before:
                    raise StackExchangeError("Stack Exchange records did not match the requested historical query.", category="schema")
                return interval_records

        if has_more:
            if start_epoch >= end_epoch:
                raise StackExchangeError("Stack Exchange results exceed the pagination cap for one second.", category="coverage")
            midpoint = start_epoch + (end_epoch - start_epoch) // 2
            left = await self._fetch_complete_interval(
                tag=tag, start_epoch=start_epoch, end_epoch=midpoint, result=result,
                archive_response=archive_response,
            )
            right = await self._fetch_complete_interval(
                tag=tag, start_epoch=midpoint + 1, end_epoch=end_epoch, result=result,
                archive_response=archive_response,
            )
            left.update(right)
            return left
        return interval_records
