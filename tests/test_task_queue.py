"""Tests for in-memory async task queue."""

import asyncio
import pytest
from app.queue.task_queue import TaskQueue, QueueTask, TaskStatus


@pytest.mark.asyncio
async def test_queue_enqueue_and_process():
    queue = TaskQueue(num_workers=2)
    processed_items = []

    async def handle_sample(payload):
        item = payload.get("item")
        processed_items.append(item)
        return {"processed": item}

    queue.register_handler("sample_task", handle_sample)
    await queue.start_workers()

    task1 = QueueTask(task_type="sample_task", payload={"item": "A"})
    task2 = QueueTask(task_type="sample_task", payload={"item": "B"})

    id1 = await queue.enqueue(task1)
    id2 = await queue.enqueue(task2)

    await queue.shutdown()

    assert "A" in processed_items
    assert "B" in processed_items

    res1 = queue.get_task_result(id1)
    assert res1 is not None
    assert res1.status == TaskStatus.COMPLETED
    assert res1.result == {"processed": "A"}

    status = queue.get_status()
    assert status.completed == 2
    assert status.failed == 0


@pytest.mark.asyncio
async def test_queue_error_handling():
    queue = TaskQueue(num_workers=1)

    async def handle_failing(payload):
        raise ValueError("Task execution failed intentionally")

    queue.register_handler("fail_task", handle_failing)
    await queue.start_workers()

    task = QueueTask(task_type="fail_task", payload={})
    task_id = await queue.enqueue(task)

    await queue.shutdown()

    res = queue.get_task_result(task_id)
    assert res is not None
    assert res.status == TaskStatus.FAILED
    assert "Task execution failed intentionally" in res.error

    status = queue.get_status()
    assert status.failed == 1
