"""Background scheduler for continuous discovery and data freshness.

Uses APScheduler for:
  - Daily: refresh stats, engagement, scores, status for active creators
  - Weekly: graph traversal for new creator discovery
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class DiscoveryScheduler:
    """Background scheduler for continuous discovery and refresh."""

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()
        self._running = False

    def start(self) -> None:
        """Start the scheduler with daily and weekly jobs."""
        if self._running:
            return

        # Daily refresh at 2 AM
        self.scheduler.add_job(
            self.daily_refresh,
            CronTrigger(hour=2, minute=0),
            id="daily_refresh",
            name="Daily Stats Refresh",
            replace_existing=True,
        )

        # Weekly deep discovery on Monday at 3 AM
        self.scheduler.add_job(
            self.weekly_discovery,
            CronTrigger(day_of_week="mon", hour=3, minute=0),
            id="weekly_discovery",
            name="Weekly Graph Discovery",
            replace_existing=True,
        )

        self.scheduler.start()
        self._running = True
        logger.info("Discovery scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Discovery scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def daily_refresh(self) -> None:
        """Daily job: update stats, engagement, scores, and status for active creators.

        This method is a placeholder — the actual implementation will import
        and use the pipeline orchestrator once the full system is wired up.
        """
        logger.info(
            "Daily refresh started at %s",
            datetime.now(timezone.utc).isoformat(),
        )
        try:
            # Import here to avoid circular imports
            from app.pipelines.discovery import DiscoveryPipeline

            pipeline = DiscoveryPipeline()
            await pipeline.refresh_active_creators()

            logger.info("Daily refresh completed successfully")
        except Exception as e:
            logger.error("Daily refresh failed: %s", e, exc_info=True)

    async def weekly_discovery(self) -> None:
        """Weekly job: traverse creator graph to find new channels.

        Looks at collaborations, mentions, featured channels from
        existing creators to discover new ones.
        """
        logger.info(
            "Weekly discovery started at %s",
            datetime.now(timezone.utc).isoformat(),
        )
        try:
            from app.pipelines.discovery import DiscoveryPipeline

            pipeline = DiscoveryPipeline()
            await pipeline.graph_expansion()

            logger.info("Weekly discovery completed successfully")
        except Exception as e:
            logger.error("Weekly discovery failed: %s", e, exc_info=True)
