"""Lightweight, maintainable scheduler for market data collection."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import Settings, get_settings
from app.models.skill_intelligence import MarketCollectionResponse
from app.services.market_collection_service import collect_market_data

logger = logging.getLogger(__name__)


class MarketDataScheduler:
    """Schedules periodic market data collection runs.

    Architecture:
        Scheduler
           ↓
        Market Collection Service
           ↓
        Providers
           ↓
        Raw Archive
           ↓
        Observations -> Firestore
    """

    def __init__(
        self,
        settings: Settings | None = None,
        interval_seconds: float | None = None,
    ):
        self.settings = settings or get_settings()
        self.interval_seconds = (
            interval_seconds
            if interval_seconds is not None
            else float(self.settings.market_collection_cadence_hours * 3600)
        )
        self._task: asyncio.Task | None = None
        self._running: bool = False
        self._last_run_at: datetime | None = None
        self._next_run_at: datetime | None = None
        self._last_result: MarketCollectionResponse | None = None
        self._run_count: int = 0

    @property
    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    async def run_once(self) -> MarketCollectionResponse:
        """Execute a single collection run via the market collection service."""
        now = datetime.now(timezone.utc)
        self._last_run_at = now
        try:
            result = await collect_market_data(
                settings=self.settings,
                location=self.settings.market_collection_target_location,
                country=self.settings.market_collection_target_country,
                query=self.settings.market_collection_query,
            )
            self._last_result = result
            self._run_count += 1
            return result
        except Exception:
            logger.error("scheduled_market_collection_failed")
            raise

    async def start(self) -> None:
        """Start the periodic collection loop in a background task."""
        if self.is_running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Gracefully stop the background collection task."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.run_once()
            except Exception:
                logger.error("scheduled_collection_iteration_error")
            self._next_run_at = datetime.now(timezone.utc) + timedelta(seconds=self.interval_seconds)
            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    def status(self) -> dict[str, Any]:
        """Return scheduler runtime metadata without exposing credentials."""
        return {
            "is_running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "cadence_hours": self.interval_seconds / 3600.0,
            "last_run_at": self._last_run_at,
            "next_run_at": self._next_run_at,
            "run_count": self._run_count,
            "last_status": self._last_result.status if self._last_result else None,
        }
