"""Unit tests for RetryAdapter.

Tests retry-with-error-feedback logic without any real LLM calls.
All adapter interactions are fully mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import dspy
import pytest
from dspy.utils.exceptions import AdapterParseError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signature() -> type:
	"""Return a minimal DSPy signature for testing."""
	return dspy.Signature("input_text -> output_text")


def _make_parse_error(
	msg: str = "bad format",
	lm_response: str = "<wrong>oops</wrong>",
) -> AdapterParseError:
	"""Build an AdapterParseError with realistic fields."""
	return AdapterParseError(
		adapter_name="XMLAdapter",
		signature=_make_signature(),
		lm_response=lm_response,
		message=msg,
	)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRetryAdapterSuccess:
	"""Main adapter succeeds on first try -- no retry needed."""

	def test_returns_result_no_retry(self):
		"""When the main adapter succeeds, its result is returned directly."""
		from lerim.agents.retry_adapter import RetryAdapter

		main_adapter = MagicMock(return_value=[{"output_text": "hello"}])
		adapter = RetryAdapter(main_adapter, max_retries=2)

		result = adapter(
			lm=MagicMock(),
			lm_kwargs={},
			signature=_make_signature(),
			demos=[],
			inputs={"input_text": "test"},
		)

		assert result == [{"output_text": "hello"}]
		assert main_adapter.call_count == 1


class TestRetryAdapterRetrySucceeds:
	"""Main adapter fails once, retry succeeds."""

	def test_returns_result_from_retry(self):
		"""After initial failure the retry call succeeds and returns its result."""
		from lerim.agents.retry_adapter import RetryAdapter

		call_count = 0

		def side_effect(lm, lm_kwargs, signature, demos, inputs):
			nonlocal call_count
			call_count += 1
			if call_count == 1:
				raise _make_parse_error()
			return [{"output_text": "recovered"}]

		main_adapter = MagicMock(side_effect=side_effect)
		adapter = RetryAdapter(main_adapter, max_retries=2)

		result = adapter(
			lm=MagicMock(),
			lm_kwargs={},
			signature=_make_signature(),
			demos=[],
			inputs={"input_text": "test"},
		)

		assert result == [{"output_text": "recovered"}]
		# 1 initial + 1 retry = 2 calls
		assert call_count == 2


class TestRetryAdapterAllFail:
	"""Main adapter fails, all retries also fail."""

	def test_raises_adapter_parse_error(self):
		"""When all attempts fail, the last AdapterParseError is raised."""
		from lerim.agents.retry_adapter import RetryAdapter

		main_adapter = MagicMock(
			side_effect=_make_parse_error("persistent failure")
		)
		adapter = RetryAdapter(main_adapter, max_retries=2)

		with pytest.raises(AdapterParseError, match="persistent failure"):
			adapter(
				lm=MagicMock(),
				lm_kwargs={},
				signature=_make_signature(),
				demos=[],
				inputs={"input_text": "test"},
			)

		# 1 initial + 2 retries = 3 calls
		assert main_adapter.call_count == 3

	def test_raises_last_error(self):
		"""The raised error is from the last retry, not the first attempt."""
		from lerim.agents.retry_adapter import RetryAdapter

		attempt = 0

		def side_effect(lm, lm_kwargs, signature, demos, inputs):
			nonlocal attempt
			attempt += 1
			raise _make_parse_error(
				msg=f"failure #{attempt}",
				lm_response=f"bad response #{attempt}",
			)

		main_adapter = MagicMock(side_effect=side_effect)
		adapter = RetryAdapter(main_adapter, max_retries=2)

		with pytest.raises(AdapterParseError, match="failure #3"):
			adapter(
				lm=MagicMock(),
				lm_kwargs={},
				signature=_make_signature(),
				demos=[],
				inputs={"input_text": "test"},
			)


class TestRetryAdapterDisablesFallback:
	"""RetryAdapter disables use_json_adapter_fallback on the main adapter."""

	def test_disables_json_fallback_on_init(self):
		"""Constructor sets use_json_adapter_fallback = False."""
		from lerim.agents.retry_adapter import RetryAdapter

		main_adapter = MagicMock()
		main_adapter.use_json_adapter_fallback = True

		RetryAdapter(main_adapter, max_retries=1)

		assert main_adapter.use_json_adapter_fallback is False

	def test_no_error_when_attr_missing(self):
		"""Constructor does not crash if main adapter lacks the attribute."""
		from lerim.agents.retry_adapter import RetryAdapter

		main_adapter = MagicMock(spec=[])  # no attributes at all
		# Should not raise
		RetryAdapter(main_adapter, max_retries=1)


class TestRetryAdapterInjectsErrorFeedback:
	"""Retry injects previous_response and error_message into inputs."""

	def test_retry_inputs_contain_error_feedback(self):
		"""On retry, the inputs dict includes previous_response and error_message."""
		from lerim.agents.retry_adapter import RetryAdapter

		captured_inputs = {}
		call_count = 0

		def side_effect(lm, lm_kwargs, signature, demos, inputs):
			nonlocal call_count, captured_inputs
			call_count += 1
			if call_count == 1:
				raise _make_parse_error(
					msg="wrong tags",
					lm_response="<tool>bad</tool>",
				)
			captured_inputs = dict(inputs)
			return [{"output_text": "fixed"}]

		main_adapter = MagicMock(side_effect=side_effect)
		adapter = RetryAdapter(main_adapter, max_retries=1)

		adapter(
			lm=MagicMock(),
			lm_kwargs={},
			signature=_make_signature(),
			demos=[],
			inputs={"input_text": "test"},
		)

		assert "previous_response" in captured_inputs
		assert captured_inputs["previous_response"] == "<tool>bad</tool>"
		assert "error_message" in captured_inputs
		assert "wrong tags" in captured_inputs["error_message"]
		# Original input is preserved
		assert captured_inputs["input_text"] == "test"

	def test_retry_signature_has_feedback_fields(self):
		"""On retry, the signature passed to the adapter has the two extra fields."""
		from lerim.agents.retry_adapter import RetryAdapter

		captured_signature = None
		call_count = 0

		def side_effect(lm, lm_kwargs, signature, demos, inputs):
			nonlocal call_count, captured_signature
			call_count += 1
			if call_count == 1:
				raise _make_parse_error()
			captured_signature = signature
			return [{"output_text": "ok"}]

		main_adapter = MagicMock(side_effect=side_effect)
		adapter = RetryAdapter(main_adapter, max_retries=1)

		adapter(
			lm=MagicMock(),
			lm_kwargs={},
			signature=_make_signature(),
			demos=[],
			inputs={"input_text": "test"},
		)

		assert captured_signature is not None
		assert "previous_response" in captured_signature.input_fields
		assert "error_message" in captured_signature.input_fields

	def test_error_feedback_updates_across_retries(self):
		"""Each retry gets the error from the immediately preceding attempt."""
		from lerim.agents.retry_adapter import RetryAdapter

		captured_inputs_list = []
		attempt = 0

		def side_effect(lm, lm_kwargs, signature, demos, inputs):
			nonlocal attempt
			attempt += 1
			if attempt <= 3:
				captured_inputs_list.append(dict(inputs))
				raise _make_parse_error(
					msg=f"error #{attempt}",
					lm_response=f"response #{attempt}",
				)
			captured_inputs_list.append(dict(inputs))
			return [{"output_text": "finally"}]

		main_adapter = MagicMock(side_effect=side_effect)
		adapter = RetryAdapter(main_adapter, max_retries=3)

		adapter(
			lm=MagicMock(),
			lm_kwargs={},
			signature=_make_signature(),
			demos=[],
			inputs={"input_text": "test"},
		)

		# First retry (index 1) should carry error from attempt 1
		assert captured_inputs_list[1]["previous_response"] == "response #1"
		assert "error #1" in captured_inputs_list[1]["error_message"]

		# Second retry (index 2) should carry error from attempt 2
		assert captured_inputs_list[2]["previous_response"] == "response #2"
		assert "error #2" in captured_inputs_list[2]["error_message"]


class TestRetryAdapterDelegation:
	"""__getattr__ delegates to main adapter."""

	def test_delegates_attribute_access(self):
		"""Accessing an unknown attribute returns the main adapter's attribute."""
		from lerim.agents.retry_adapter import RetryAdapter

		main_adapter = MagicMock()
		main_adapter.format_prompt = "custom_formatter"
		adapter = RetryAdapter(main_adapter, max_retries=1)

		assert adapter.format_prompt == "custom_formatter"

	def test_delegates_method_call(self):
		"""Calling a method on RetryAdapter calls through to main adapter."""
		from lerim.agents.retry_adapter import RetryAdapter

		main_adapter = MagicMock()
		main_adapter.some_method.return_value = 42
		adapter = RetryAdapter(main_adapter, max_retries=1)

		result = adapter.some_method("arg1", key="val")

		main_adapter.some_method.assert_called_once_with("arg1", key="val")
		assert result == 42

	def test_own_attributes_not_delegated(self):
		"""RetryAdapter's own attributes (main_adapter, max_retries) are direct."""
		from lerim.agents.retry_adapter import RetryAdapter

		main_adapter = MagicMock()
		adapter = RetryAdapter(main_adapter, max_retries=5)

		assert adapter.main_adapter is main_adapter
		assert adapter.max_retries == 5
