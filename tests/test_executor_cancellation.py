"""Tests for AgentExecutor cancellation result storage."""

import asyncio
import pytest
from src.agent.executor import AgentExecutor


@pytest.mark.asyncio
async def test_cancelled_execution_stores_result():
    """Cancelled executions should leave a clear result object in _results."""
    executor = AgentExecutor(max_concurrent=2)

    async def slow_handler(agent_id, task):
        await asyncio.sleep(10)  # Simulate long-running task
        return {"done": True}

    # Start execution in background
    exec_task = asyncio.create_task(
        executor.execute("agent-1", {"id": "task-1"}, slow_handler)
    )
    await asyncio.sleep(0.05)  # Let the task start

    # Get the execution_id from active tasks
    execution_id = list(executor._active_tasks.keys())[0]

    # Cancel the execution
    result = executor.cancel(execution_id)
    assert result is True

    # Wait for cancellation to propagate
    await asyncio.sleep(0.1)

    # The result should be stored with a cancelled status
    stored = executor.get_result(execution_id)
    assert stored is not None
    assert stored["status"] in ("cancelled", "cancelling")
    assert "cancelled_at" in stored

    # Clean up
    try:
        await exec_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_cancel_nonexistent_returns_false():
    """Cancelling a non-existent execution should return False."""
    executor = AgentExecutor()
    assert executor.cancel("nonexistent-id") is False


@pytest.mark.asyncio
async def test_normal_execution_stores_result():
    """Normal completion should still store results correctly."""
    executor = AgentExecutor()

    async def fast_handler(agent_id, task):
        return {"value": 42}

    execution_id = await executor.execute("agent-1", {"id": "task-1"}, fast_handler)
    result = executor.get_result(execution_id)
    assert result is not None
    assert result["result"] == {"value": 42}
