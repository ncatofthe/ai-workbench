"""Tests for staged step execution safety and correctness.

Uses unittest with stdlib mocks — no pytest dependency required for syntax/logic
validation. Full execution requires pytest + project dependencies.
"""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# These tests can run standalone for logic validation.
# With pytest + installed deps they also verify integration.

try:
    from src.models import RunStatus, RunStep
    from src.orchestrator.engine import (
        MAX_CONSECUTIVE_FAILURES,
        MAX_EXECUTABLE_STEPS,
        STEP_TIMEOUT_SECONDS,
        TOTAL_EXECUTION_TIMEOUT_SECONDS,
        _execute_staged_steps,
        extract_executable_tasks,
        stage_executable_task_steps,
    )

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


def _make_step(
    step_id: str,
    title: str = "Test step",
    status: str = "pending",
    agent_id: str = "orchestrator",
    input_text: str = "do something",
) -> "RunStep":
    return RunStep(
        id=step_id,
        run_id="run-1",
        parent_step_id="parent-1",
        agent_id=agent_id,
        status=status,
        title=title,
        input=input_text,
        created_at=datetime.now().isoformat(),
    )


@unittest.skipUnless(HAS_DEPS, "Project dependencies not installed")
class TestStagedExecutionSafety(unittest.TestCase):
    """Test safety limits in _execute_staged_steps."""

    def setUp(self):
        self.log_messages: list[str] = []
        self.log_fn = self.log_messages.append
        self.base_kwargs = dict(
            run_id="run-1",
            instructions="You are a helpful agent.",
            product_spec="spec",
            plan_text="plan",
            architecture_text="arch",
            task_breakdown="tasks",
            project_stack="python",
            ollama_model="test-model",
            ollama_base_url="http://localhost:11434",
            log_fn=self.log_fn,
        )

    @patch("src.orchestrator.engine.update_run")
    @patch("src.orchestrator.engine.update_run_step")
    @patch("src.orchestrator.engine.ollama")
    def test_skip_completed_steps(self, mock_ollama, mock_update_step, mock_update_run):
        """Already-completed steps must be skipped, not re-executed."""
        mock_ollama.chat_completion = AsyncMock(return_value="output")
        steps = [
            _make_step("s1", "Completed step", status="completed"),
            _make_step("s2", "Pending step", status="pending"),
        ]
        result = asyncio.get_event_loop().run_until_complete(
            _execute_staged_steps(staged_steps=steps, **self.base_kwargs)
        )
        self.assertEqual(result, 1)  # Only 1 executed (s2)
        self.assertTrue(any("Skipping" in m for m in self.log_messages))

    @patch("src.orchestrator.engine.update_run")
    @patch("src.orchestrator.engine.update_run_step")
    @patch("src.orchestrator.engine.ollama")
    def test_skip_failed_steps(self, mock_ollama, mock_update_step, mock_update_run):
        """Already-failed steps must be skipped."""
        mock_ollama.chat_completion = AsyncMock(return_value="output")
        steps = [
            _make_step("s1", "Failed step", status="failed"),
            _make_step("s2", "Pending step", status="pending"),
        ]
        result = asyncio.get_event_loop().run_until_complete(
            _execute_staged_steps(staged_steps=steps, **self.base_kwargs)
        )
        self.assertEqual(result, 1)

    @patch("src.orchestrator.engine.update_run")
    @patch("src.orchestrator.engine.update_run_step")
    @patch("src.orchestrator.engine.ollama")
    def test_single_step_failure_does_not_crash_run(self, mock_ollama, mock_update_step, mock_update_run):
        """A single failing step should not prevent other steps from executing."""
        call_count = 0

        async def flaky_completion(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Ollama connection lost")
            return f"output-{call_count}"

        mock_ollama.chat_completion = flaky_completion
        steps = [_make_step(f"s{i}", f"Step {i}") for i in range(3)]
        result = asyncio.get_event_loop().run_until_complete(
            _execute_staged_steps(staged_steps=steps, **self.base_kwargs)
        )
        self.assertEqual(result, 2)  # s1 and s3 succeed, s2 fails
        # Verify the failed step was marked as failed
        failed_calls = [
            c for c in mock_update_step.call_args_list
            if c[1].get("status") == RunStatus.FAILED.value
        ]
        self.assertEqual(len(failed_calls), 1)

    @patch("src.orchestrator.engine.update_run")
    @patch("src.orchestrator.engine.update_run_step")
    @patch("src.orchestrator.engine.ollama")
    def test_consecutive_failure_breaker(self, mock_ollama, mock_update_step, mock_update_run):
        """Execution stops after MAX_CONSECUTIVE_FAILURES in a row."""
        mock_ollama.chat_completion = AsyncMock(side_effect=RuntimeError("always fails"))
        steps = [_make_step(f"s{i}", f"Step {i}") for i in range(6)]
        result = asyncio.get_event_loop().run_until_complete(
            _execute_staged_steps(staged_steps=steps, **self.base_kwargs)
        )
        self.assertEqual(result, 0)
        # Should have stopped after MAX_CONSECUTIVE_FAILURES, not all 6
        running_calls = [
            c for c in mock_update_step.call_args_list
            if len(c[0]) > 0 and c[1].get("status") == RunStatus.RUNNING.value
        ]
        self.assertEqual(len(running_calls), MAX_CONSECUTIVE_FAILURES)

    @patch("src.orchestrator.engine.update_run")
    @patch("src.orchestrator.engine.update_run_step")
    @patch("src.orchestrator.engine.ollama")
    def test_max_steps_cap(self, mock_ollama, mock_update_step, mock_update_run):
        """No more than MAX_EXECUTABLE_STEPS should execute."""
        mock_ollama.chat_completion = AsyncMock(return_value="ok")
        steps = [_make_step(f"s{i}", f"Step {i}") for i in range(20)]
        result = asyncio.get_event_loop().run_until_complete(
            _execute_staged_steps(staged_steps=steps, **self.base_kwargs)
        )
        self.assertEqual(result, MAX_EXECUTABLE_STEPS)
        self.assertTrue(any("exceed limit" in m for m in self.log_messages))

    @patch("src.orchestrator.engine.update_run")
    @patch("src.orchestrator.engine.update_run_step")
    @patch("src.orchestrator.engine.ollama")
    def test_step_timeout(self, mock_ollama, mock_update_step, mock_update_run):
        """A step that exceeds STEP_TIMEOUT_SECONDS should fail with timeout."""

        async def slow_completion(**kwargs):
            await asyncio.sleep(999)
            return "never"

        mock_ollama.chat_completion = slow_completion
        steps = [_make_step("s1", "Slow step")]

        # Patch timeout to 0.1s for test speed
        with patch("src.orchestrator.engine.STEP_TIMEOUT_SECONDS", 0.1):
            result = asyncio.get_event_loop().run_until_complete(
                _execute_staged_steps(staged_steps=steps, **self.base_kwargs)
            )
        self.assertEqual(result, 0)
        timeout_calls = [
            c for c in mock_update_step.call_args_list
            if "timed out" in str(c[1].get("error", ""))
        ]
        self.assertEqual(len(timeout_calls), 1)

    @patch("src.orchestrator.engine.update_run")
    @patch("src.orchestrator.engine.update_run_step")
    @patch("src.orchestrator.engine.ollama")
    def test_cancellation_propagates(self, mock_ollama, mock_update_step, mock_update_run):
        """CancelledError should be re-raised, not swallowed."""

        async def cancelled_completion(**kwargs):
            raise asyncio.CancelledError()

        mock_ollama.chat_completion = cancelled_completion
        steps = [_make_step("s1", "Step")]
        with self.assertRaises(asyncio.CancelledError):
            asyncio.get_event_loop().run_until_complete(
                _execute_staged_steps(staged_steps=steps, **self.base_kwargs)
            )
        # Step should be marked as stopped
        stopped_calls = [
            c for c in mock_update_step.call_args_list
            if c[1].get("status") == RunStatus.STOPPED.value
        ]
        self.assertEqual(len(stopped_calls), 1)


@unittest.skipUnless(HAS_DEPS, "Project dependencies not installed")
class TestSafetyConstants(unittest.TestCase):
    """Verify safety constants are set to reasonable values."""

    def test_max_steps_reasonable(self):
        self.assertGreaterEqual(MAX_EXECUTABLE_STEPS, 1)
        self.assertLessEqual(MAX_EXECUTABLE_STEPS, 50)

    def test_step_timeout_reasonable(self):
        self.assertGreaterEqual(STEP_TIMEOUT_SECONDS, 30)
        self.assertLessEqual(STEP_TIMEOUT_SECONDS, 600)

    def test_total_timeout_reasonable(self):
        self.assertGreaterEqual(TOTAL_EXECUTION_TIMEOUT_SECONDS, 60)
        self.assertLessEqual(TOTAL_EXECUTION_TIMEOUT_SECONDS, 3600)

    def test_consecutive_failures_reasonable(self):
        self.assertGreaterEqual(MAX_CONSECUTIVE_FAILURES, 1)
        self.assertLessEqual(MAX_CONSECUTIVE_FAILURES, 10)

    def test_total_timeout_exceeds_single_step(self):
        self.assertGreater(TOTAL_EXECUTION_TIMEOUT_SECONDS, STEP_TIMEOUT_SECONDS)


@unittest.skipUnless(HAS_DEPS, "Project dependencies not installed")
class TestExtractExecutableTasks(unittest.TestCase):
    """Test Markdown task extraction logic."""

    def test_extracts_ordered_list(self):
        md = "## Ordered Tasks\n\n1. First task\n2. Second task\n3. Third task\n"
        tasks = extract_executable_tasks(md)
        self.assertEqual(tasks, ["First task", "Second task", "Third task"])

    def test_extracts_bullet_list(self):
        md = "## Ordered Tasks\n\n- Do A\n- Do B\n"
        tasks = extract_executable_tasks(md)
        self.assertEqual(tasks, ["Do A", "Do B"])

    def test_respects_max_steps(self):
        md = "## Ordered Tasks\n\n" + "".join(f"- Task {i}\n" for i in range(20))
        tasks = extract_executable_tasks(md, max_steps=5)
        self.assertEqual(len(tasks), 5)

    def test_deduplicates(self):
        md = "## Ordered Tasks\n\n- Same task\n- Same task\n- Different task\n"
        tasks = extract_executable_tasks(md)
        self.assertEqual(tasks, ["Same task", "Different task"])

    def test_empty_input(self):
        tasks = extract_executable_tasks("")
        self.assertEqual(tasks, [])

    def test_no_ordered_tasks_section_falls_back(self):
        md = "- Global task 1\n- Global task 2\n"
        tasks = extract_executable_tasks(md)
        self.assertEqual(tasks, ["Global task 1", "Global task 2"])


if __name__ == "__main__":
    unittest.main()
