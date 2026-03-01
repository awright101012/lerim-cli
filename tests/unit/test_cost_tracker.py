"""Unit tests for runtime cost tracker: accumulator, hooks, and DSPy capture."""

from __future__ import annotations

import httpx
import pytest

from lerim.runtime.cost_tracker import (
    _run_cost,
    add_cost,
    build_tracked_async_client,
    capture_dspy_cost,
    start_cost_tracking,
    stop_cost_tracking,
)


def _reset():
    """Ensure cost tracking is off before each test."""
    _run_cost.set(None)


class TestAccumulator:
    """start/stop/add_cost lifecycle."""

    def setup_method(self):
        """Reset cost tracking before each test."""
        _reset()

    def teardown_method(self):
        """Clean up cost tracking after each test."""
        _reset()

    def test_start_stop_zero(self):
        """Fresh accumulator returns 0.0."""
        start_cost_tracking()
        assert stop_cost_tracking() == 0.0

    def test_add_cost_accumulates(self):
        """Multiple add_cost calls sum correctly."""
        start_cost_tracking()
        add_cost(0.001)
        add_cost(0.002)
        add_cost(0.0005)
        assert stop_cost_tracking() == pytest.approx(0.0035)

    def test_stop_clears_accumulator(self):
        """After stop, a new start begins at zero."""
        start_cost_tracking()
        add_cost(1.0)
        stop_cost_tracking()
        start_cost_tracking()
        assert stop_cost_tracking() == 0.0

    def test_add_cost_noop_when_not_tracking(self):
        """add_cost does nothing when tracking is not active."""
        add_cost(999.0)  # should not raise
        start_cost_tracking()
        assert stop_cost_tracking() == 0.0

    def test_stop_without_start_returns_zero(self):
        """stop_cost_tracking returns 0.0 when never started."""
        assert stop_cost_tracking() == 0.0


class TestCaptureHook:
    """_capture_cost_hook extracts cost from httpx responses."""

    def setup_method(self):
        """Reset cost tracking before each test."""
        _reset()

    def teardown_method(self):
        """Clean up cost tracking after each test."""
        _reset()

    @pytest.mark.anyio
    async def test_hook_captures_cost_from_json(self):
        """Hook extracts usage.cost from a 200 JSON response."""
        start_cost_tracking()
        client = build_tracked_async_client()
        hooks = client.event_hooks["response"]
        assert len(hooks) == 1
        hook = hooks[0]

        # Build a mock response with usage.cost
        response = httpx.Response(
            200,
            json={
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0042}
            },
            headers={"content-type": "application/json"},
            request=httpx.Request(
                "POST", "https://openrouter.ai/api/v1/chat/completions"
            ),
        )
        await hook(response)
        assert stop_cost_tracking() == pytest.approx(0.0042)

    @pytest.mark.anyio
    async def test_hook_ignores_non_200(self):
        """Hook skips non-200 responses."""
        start_cost_tracking()
        hook = build_tracked_async_client().event_hooks["response"][0]

        response = httpx.Response(
            429,
            json={"error": "rate limited"},
            headers={"content-type": "application/json"},
            request=httpx.Request(
                "POST", "https://openrouter.ai/api/v1/chat/completions"
            ),
        )
        await hook(response)
        assert stop_cost_tracking() == 0.0

    @pytest.mark.anyio
    async def test_hook_ignores_non_json(self):
        """Hook skips responses without application/json content type."""
        start_cost_tracking()
        hook = build_tracked_async_client().event_hooks["response"][0]

        response = httpx.Response(
            200,
            text="data: {}\n\n",
            headers={"content-type": "text/event-stream"},
            request=httpx.Request(
                "POST", "https://openrouter.ai/api/v1/chat/completions"
            ),
        )
        await hook(response)
        assert stop_cost_tracking() == 0.0

    @pytest.mark.anyio
    async def test_hook_ignores_missing_usage(self):
        """Hook handles JSON without usage field gracefully."""
        start_cost_tracking()
        hook = build_tracked_async_client().event_hooks["response"][0]

        response = httpx.Response(
            200,
            json={"choices": []},
            headers={"content-type": "application/json"},
            request=httpx.Request(
                "POST", "https://openrouter.ai/api/v1/chat/completions"
            ),
        )
        await hook(response)
        assert stop_cost_tracking() == 0.0


class TestCaptureDspyCost:
    """capture_dspy_cost reads cost from DSPy LM history."""

    def setup_method(self):
        """Reset cost tracking before each test."""
        _reset()

    def teardown_method(self):
        """Clean up cost tracking after each test."""
        _reset()

    def test_captures_cost_from_history(self):
        """Reads cost from response.usage.cost in LM history entries."""

        class FakeUsage:
            cost = 0.005

        class FakeResponse:
            usage = FakeUsage()

        class FakeLM:
            history = [
                {"response": FakeResponse()},
                {"response": FakeResponse()},
            ]

        start_cost_tracking()
        capture_dspy_cost(FakeLM(), history_start=0)
        assert stop_cost_tracking() == pytest.approx(0.01)

    def test_respects_history_start(self):
        """Only captures cost from entries after history_start."""

        class FakeUsage:
            cost = 0.003

        class FakeResponse:
            usage = FakeUsage()

        class FakeLM:
            history = [
                {"response": FakeResponse()},
                {"response": FakeResponse()},
                {"response": FakeResponse()},
            ]

        start_cost_tracking()
        capture_dspy_cost(FakeLM(), history_start=2)
        assert stop_cost_tracking() == pytest.approx(0.003)

    def test_handles_no_history(self):
        """No-op when LM has no history attribute."""
        start_cost_tracking()
        capture_dspy_cost(object(), history_start=0)
        assert stop_cost_tracking() == 0.0

    def test_handles_dict_usage(self):
        """Handles usage as a dict (fallback path)."""

        class FakeResponse:
            usage = {"cost": 0.007}

        class FakeLM:
            history = [{"response": FakeResponse()}]

        start_cost_tracking()
        # usage is a dict but getattr(usage, "cost") returns None for dicts,
        # so the fallback dict.get path is exercised
        capture_dspy_cost(FakeLM(), history_start=0)
        assert stop_cost_tracking() == pytest.approx(0.007)

    def test_skips_entries_without_response(self):
        """Entries missing 'response' key are skipped."""

        class FakeLM:
            history = [{"no_response": True}, {"response": None}]

        start_cost_tracking()
        capture_dspy_cost(FakeLM(), history_start=0)
        assert stop_cost_tracking() == 0.0
