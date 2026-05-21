"""Task Scheduler — Priority-based task queuing and dispatch."""

import asyncio
import heapq
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Maximum consecutive failures before a job is considered "poison"
POISON_THRESHOLD = 3

# Exponential backoff base delay in seconds
BACKOFF_BASE = 2.0

# Maximum backoff delay (cap at 5 minutes)
BACKOFF_MAX = 300.0

# Maximum redelivery rate per queue (jobs per second)
MAX_REDELIVERY_RATE = 10


class PriorityQueue:
    def __init__(self):
        self._queue = []
        self._counter = 0

    def push(self, item: Any, priority: int = 0) -> None:
        heapq.heappush(self._queue, (-priority, self._counter, item))
        self._counter += 1

    def pop(self) -> Optional[Any]:
        if self._queue:
            return heapq.heappop(self._queue)[2]
        return None

    def peek(self) -> Optional[Any]:
        if self._queue:
            return self._queue[0][2]
        return None

    def __len__(self) -> int:
        return len(self._queue)


class TaskScheduler:
    def __init__(self, max_retries: int = 3):
        self._queues: Dict[str, PriorityQueue] = {}
        self._scheduled: Dict[str, float] = {}
        self._in_flight: Dict[str, Dict] = {}
        self._max_retries = max_retries
        # Poison job tracking
        self._poison_jobs: Dict[str, Dict] = {}  # task_id -> poison info
        self._dead_letter: List[Dict] = []
        # Redelivery throttling
        self._redelivery_timestamps: Dict[str, List[float]] = {}  # queue -> [timestamps]

    def _compute_backoff(self, retries: int) -> float:
        """Compute exponential backoff delay for retry."""
        delay = BACKOFF_BASE * (2 ** retries)
        return min(delay, BACKOFF_MAX)

    def _is_throttled(self, queue: str) -> bool:
        """Check if redelivery is throttled for this queue."""
        now = time.time()
        if queue not in self._redelivery_timestamps:
            self._redelivery_timestamps[queue] = []

        # Keep only timestamps from the last second
        self._redelivery_timestamps[queue] = [
            t for t in self._redelivery_timestamps[queue] if now - t < 1.0
        ]

        return len(self._redelivery_timestamps[queue]) >= MAX_REDELIVERY_RATE

    def _record_redelivery(self, queue: str) -> None:
        """Record a redelivery event for throttling."""
        if queue not in self._redelivery_timestamps:
            self._redelivery_timestamps[queue] = []
        self._redelivery_timestamps[queue].append(time.time())

    def enqueue(self, task: Dict, queue: str = "default", priority: int = 0) -> str:
        task_id = str(uuid4())
        task["id"] = task_id
        task["enqueued_at"] = time.time()
        task["retries"] = task.get("retries", 0)

        if queue not in self._queues:
            self._queues[queue] = PriorityQueue()
        self._queues[queue].push(task, priority)
        return task_id

    def schedule(self, task: Dict, delay: float, queue: str = "default", priority: int = 0) -> str:
        task_id = str(uuid4())
        task["id"] = task_id
        self._scheduled[task_id] = time.time() + delay
        return task_id

    async def dequeue(self, queue: str = "default", timeout: float = 1.0) -> Optional[Dict]:
        now = time.time()
        expired = [tid for tid, t in self._scheduled.items() if t <= now]
        for tid in expired:
            task = self._scheduled.pop(tid)
            if task:
                self.enqueue(task, queue)

        if queue in self._queues and len(self._queues[queue]) > 0:
            task = self._queues[queue].pop()
            if task:
                self._in_flight[task["id"]] = task
                return task
        return None

    def complete(self, task_id: str) -> bool:
        # Clear poison job tracking on success
        self._poison_jobs.pop(task_id, None)
        return self._in_flight.pop(task_id, None) is not None

    def fail(self, task_id: str, queue: str = "default") -> bool:
        """Handle task failure with poison job throttling and exponential backoff.

        - Tracks consecutive failures per task
        - Applies exponential backoff before re-enqueueing
        - Moves to dead letter queue after max retries
        - Throttles redelivery rate to prevent worker crash loops
        """
        task = self._in_flight.pop(task_id, None)
        if not task:
            return False

        task["retries"] = task.get("retries", 0) + 1
        retries = task["retries"]

        # Track poison jobs
        if task_id not in self._poison_jobs:
            self._poison_jobs[task_id] = {
                "first_failure": time.time(),
                "consecutive_failures": 0,
            }
        self._poison_jobs[task_id]["consecutive_failures"] += 1
        self._poison_jobs[task_id]["last_failure"] = time.time()

        # Check if exceeded max retries — move to dead letter
        if retries >= self._max_retries:
            self._dead_letter.append({
                **task,
                "failed_at": time.time(),
                "total_retries": retries,
                "reason": "max_retries_exceeded",
            })
            self._poison_jobs.pop(task_id, None)
            logger.warning(
                "Task %s moved to dead letter queue after %d retries",
                task_id, retries
            )
            return False

        # Check redelivery throttle to prevent worker crash loops
        if self._is_throttled(queue):
            logger.info(
                "Redelivery throttled for queue '%s': rate limit exceeded. "
                "Deferring task %s (retry %d/%d)",
                queue, task_id, retries, self._max_retries
            )
            # Schedule delayed retry with backoff
            backoff = self._compute_backoff(retries)
            task["next_retry_at"] = time.time() + backoff
            self._scheduled[task_id] = time.time() + backoff
            return True

        # Apply exponential backoff — schedule delayed retry
        backoff = self._compute_backoff(retries)
        task["next_retry_at"] = time.time() + backoff
        self._scheduled[task_id] = time.time() + backoff
        self._record_redelivery(queue)

        logger.info(
            "Task %s failed (retry %d/%d), scheduled retry after %.1fs backoff",
            task_id, retries, self._max_retries, backoff
        )
        return True

    def get_dead_letter(self) -> List[Dict]:
        """Return and clear the dead letter queue."""
        dead = self._dead_letter
        self._dead_letter = []
        return dead

    def get_poison_jobs(self) -> Dict[str, Dict]:
        """Return current poison job tracking info."""
        return dict(self._poison_jobs)

    def is_poison_job(self, task_id: str) -> bool:
        """Check if a task is flagged as a poison job."""
        info = self._poison_jobs.get(task_id)
        if info is None:
            return False
        return info["consecutive_failures"] >= POISON_THRESHOLD
