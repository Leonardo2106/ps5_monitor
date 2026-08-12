"""Minimal fallback used only when the external `schedule` package is unavailable."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class _Job:
    interval: int
    function: Callable[..., Any] | None = None
    next_run: float = 0.0
    tags: set[str] = field(default_factory=set)

    @property
    def seconds(self) -> "_Job":
        return self

    def do(self, function: Callable[..., Any]) -> "_Job":
        self.function = function
        self.next_run = time.monotonic() + self.interval
        return self

    def tag(self, *tags: str) -> "_Job":
        self.tags.update(tags)
        return self

    def run(self) -> Any:
        if self.function is None:
            return None
        result = self.function()
        self.next_run = time.monotonic() + self.interval
        return result


class Scheduler:
    """Small subset of schedule.Scheduler used by MonitorService."""

    def __init__(self) -> None:
        self.jobs: list[_Job] = []

    def every(self, interval: int = 1) -> _Job:
        job = _Job(interval=max(1, int(interval)))
        self.jobs.append(job)
        return job

    def clear(self, tag: str | None = None) -> None:
        if tag is None:
            self.jobs.clear()
        else:
            self.jobs = [job for job in self.jobs if tag not in job.tags]

    def run_pending(self) -> None:
        now = time.monotonic()
        for job in list(self.jobs):
            if job.function is not None and job.next_run <= now:
                job.run()

    def run_all(self, delay_seconds: int = 0) -> None:
        for index, job in enumerate(list(self.jobs)):
            job.run()
            if delay_seconds and index < len(self.jobs) - 1:
                time.sleep(delay_seconds)


_default_scheduler = Scheduler()


def every(interval: int = 1) -> _Job:
    return _default_scheduler.every(interval)


def clear(tag: str | None = None) -> None:
    _default_scheduler.clear(tag)


def run_pending() -> None:
    _default_scheduler.run_pending()


def run_all(delay_seconds: int = 0) -> None:
    _default_scheduler.run_all(delay_seconds)
