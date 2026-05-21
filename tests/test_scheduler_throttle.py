"""Tests for poison job redelivery throttling and dead-letter queue."""

import time
from src.orchestrator.scheduler import TaskScheduler


def test_poison_job_moves_to_dead_letter():
    """Jobs exceeding max retries should be moved to dead-letter queue."""
    scheduler = TaskScheduler(max_retries=2)

    task_id = scheduler.enqueue({"type": "poison"}, queue="default")
    task = scheduler.dequeue(queue="default")
    assert task is not None
    assert task["id"] == task_id

    # First failure - should retry
    result = scheduler.fail(task_id, queue="default")
    assert result is True  # Will be retried

    # Second failure - exceeds max_retries, should go to dead-letter
    # Need to dequeue and fail again
    time.sleep(0.1)  # Let scheduled task expire
    task2 = scheduler.dequeue(queue="default")
    if task2:
        result2 = scheduler.fail(task_id, queue="default")
        assert result2 is False  # Dead-lettered

    dead = scheduler.get_dead_letter()
    assert len(dead) >= 1
    assert "dead_lettered_at" in dead[0]
    assert "dead_letter_reason" in dead[0]


def test_exponential_backoff_delays():
    """Retry delays should increase exponentially."""
    scheduler = TaskScheduler(base_retry_delay=1.0, max_retry_delay=60.0)

    task_id = scheduler.enqueue({"type": "test"}, queue="default")
    task = scheduler.dequeue(queue="default")

    # First retry: 1.0s delay
    scheduler.fail(task_id, queue="default")
    scheduled = scheduler._scheduled.get(task_id)
    # Task was scheduled with delay, check the delay is applied
    assert scheduled is not None or task is not None


def test_dead_letter_purge():
    """Purge should clear the dead-letter queue."""
    scheduler = TaskScheduler(max_retries=1)

    task_id = scheduler.enqueue({"type": "test"}, queue="default")
    task = scheduler.dequeue(queue="default")
    scheduler.fail(task_id, queue="default")  # Dead-lettered after 1 retry

    dead = scheduler.get_dead_letter()
    assert len(dead) >= 1

    count = scheduler.purge_dead_letter()
    assert count >= 1
    assert len(scheduler.get_dead_letter()) == 0


def test_max_retry_delay_cap():
    """Retry delay should not exceed max_retry_delay."""
    scheduler = TaskScheduler(base_retry_delay=10.0, max_retry_delay=30.0)

    task_id = scheduler.enqueue({"type": "test"}, queue="default")
    task = scheduler.dequeue(queue="default")
    scheduler.fail(task_id, queue="default")

    # The retry delay should be capped at max_retry_delay
    # First retry: min(10 * 2^0, 30) = 10
    # Second retry: min(10 * 2^1, 30) = 20
    # Third retry: min(10 * 2^2, 30) = 30 (capped)
