"""Runtime registry for cancellable background runs."""

from __future__ import annotations

import asyncio

_ACTIVE_RUN_TASKS: dict[str, asyncio.Task] = {}


def register_run_task(run_id: str, task: asyncio.Task) -> None:
    existing = _ACTIVE_RUN_TASKS.get(run_id)
    if existing and not existing.done():
        existing.cancel()

    _ACTIVE_RUN_TASKS[run_id] = task
    task.add_done_callback(lambda completed: _unregister_if_current(run_id, completed))


def cancel_run_task(run_id: str) -> bool:
    task = _ACTIVE_RUN_TASKS.get(run_id)
    if not task or task.done():
        return False
    task.cancel()
    return True


def is_run_task_active(run_id: str) -> bool:
    task = _ACTIVE_RUN_TASKS.get(run_id)
    return bool(task and not task.done())


def clear_run_tasks() -> None:
    _ACTIVE_RUN_TASKS.clear()


def _unregister_if_current(run_id: str, task: asyncio.Task) -> None:
    if _ACTIVE_RUN_TASKS.get(run_id) is task:
        _ACTIVE_RUN_TASKS.pop(run_id, None)
