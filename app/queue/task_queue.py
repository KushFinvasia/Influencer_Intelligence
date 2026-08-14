"""In-memory async task queue with configurable workers.

Decouples crawling from processing. Can be swapped for Redis/RabbitMQ
later without changing worker logic.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class QueueTask(BaseModel):
    """A task to be processed by a worker."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str  # "process_profile", "enrich_llm", "refresh_stats"
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0  # Lower = higher priority
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class TaskResult(BaseModel):
    """Result of a processed task."""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class QueueStatus(BaseModel):
    """Current queue status."""
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    workers_active: int = 0


class TaskQueue:
    """In-memory async task queue with configurable workers."""

    def __init__(self, num_workers: int = 5) -> None:
        self.num_workers = num_workers
        self.queue: asyncio.Queue[QueueTask] = asyncio.Queue()
        self.workers: list[asyncio.Task] = []
        self.results: dict[str, TaskResult] = {}
        self._handlers: dict[str, Callable] = {}
        self._running = False
        self._processing_count = 0

    def register_handler(
        self,
        task_type: str,
        handler: Callable[[dict[str, Any]], Coroutine],
    ) -> None:
        """Register a handler for a task type.

        Args:
            task_type: The task type string (e.g., "process_profile").
            handler: Async function that takes payload dict and returns result dict.
        """
        self._handlers[task_type] = handler
        logger.info("Registered handler for task type: %s", task_type)

    async def enqueue(self, task: QueueTask) -> str:
        """Add a task to the queue.

        Returns the task ID for tracking.
        """
        self.results[task.task_id] = TaskResult(task_id=task.task_id)
        await self.queue.put(task)
        logger.debug(
            "Enqueued task %s (type=%s, queue_size=%d)",
            task.task_id,
            task.task_type,
            self.queue.qsize(),
        )
        return task.task_id

    async def start_workers(self) -> None:
        """Start worker coroutines."""
        if self._running:
            return
        self._running = True
        for i in range(self.num_workers):
            worker = asyncio.create_task(
                self._worker(i), name=f"queue-worker-{i}"
            )
            self.workers.append(worker)
        logger.info("Started %d queue workers", self.num_workers)

    async def _worker(self, worker_id: int) -> None:
        """Worker loop that processes tasks from the queue."""
        logger.info("Worker %d started", worker_id)
        while self._running:
            try:
                task = await asyncio.wait_for(
                    self.queue.get(), timeout=0.1
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            task_result = self.results.get(task.task_id)
            if task_result:
                task_result.status = TaskStatus.PROCESSING
                task_result.started_at = datetime.now(timezone.utc)
            self._processing_count += 1

            try:
                handler = self._handlers.get(task.task_type)
                if not handler:
                    raise ValueError(
                        f"No handler for task type: {task.task_type}"
                    )

                result = await handler(task.payload)

                if task_result:
                    task_result.status = TaskStatus.COMPLETED
                    task_result.result = result or {}
                    task_result.completed_at = datetime.now(timezone.utc)

                logger.debug(
                    "Worker %d completed task %s", worker_id, task.task_id
                )

            except Exception as e:
                logger.error(
                    "Worker %d failed task %s: %s",
                    worker_id,
                    task.task_id,
                    e,
                    exc_info=True,
                )
                if task_result:
                    task_result.status = TaskStatus.FAILED
                    task_result.error = str(e)
                    task_result.completed_at = datetime.now(timezone.utc)

            finally:
                self._processing_count -= 1
                self.queue.task_done()

    async def shutdown(self) -> None:
        """Gracefully shutdown all workers."""
        # Wait for queue to empty while workers are running
        if not self.queue.empty():
            logger.info(
                "Waiting for %d remaining tasks", self.queue.qsize()
            )
            await self.queue.join()

        self._running = False

        # Cancel workers
        for worker in self.workers:
            worker.cancel()
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        logger.info("Queue shutdown complete")

    def get_status(self) -> QueueStatus:
        """Get current queue status."""
        completed = sum(
            1
            for r in self.results.values()
            if r.status == TaskStatus.COMPLETED
        )
        failed = sum(
            1
            for r in self.results.values()
            if r.status == TaskStatus.FAILED
        )
        return QueueStatus(
            pending=self.queue.qsize(),
            processing=self._processing_count,
            completed=completed,
            failed=failed,
            workers_active=len(
                [w for w in self.workers if not w.done()]
            ),
        )

    def get_task_result(self, task_id: str) -> TaskResult | None:
        """Get the result of a specific task."""
        return self.results.get(task_id)
