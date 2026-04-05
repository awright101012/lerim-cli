"""Adapter wrapper with per-call retry and error feedback.

Ported from stanfordnlp/dspy PR #8050 (approved, unmerged as of 2026-04).
Drop this module when DSPy merges RetryAdapter into the main package.

When the wrapped adapter fails to parse an LLM response (e.g. the model
writes <tool_name> instead of <next_tool_name>), this adapter retries the
call with the failed response and error message injected into the prompt,
giving the LLM a chance to correct its formatting.
"""

from __future__ import annotations

import logging
from typing import Any

import dspy
from dspy.utils.exceptions import AdapterParseError

logger = logging.getLogger(__name__)


def _add_retry_fields(signature: type) -> type:
	"""Append previous_response and error_message InputFields to signature.

	Based on create_signature_for_retry() from dspy PR #8050.
	"""
	return (
		signature
		.append(
			"previous_response",
			dspy.InputField(
				desc=(
					"Your previous response that failed to parse. "
					"Avoid the same formatting mistake."
				),
			),
			type_=str,
		)
		.append(
			"error_message",
			dspy.InputField(desc="Error message for the previous response."),
			type_=str,
		)
	)


class RetryAdapter:
	"""Adapter wrapper that retries on parse failure with error feedback.

	Wraps a main adapter (typically dspy.XMLAdapter). On AdapterParseError,
	injects the failed LLM response and error message as extra input fields
	and retries, so the LLM can see its mistake and correct it.

	The retry happens transparently within a single ReAct iteration —
	the ReAct loop never sees the error and no trajectory work is lost.

	Usage::

		adapter = RetryAdapter(dspy.XMLAdapter(), max_retries=2)
		with dspy.context(adapter=adapter):
			prediction = agent()
	"""

	def __init__(self, main_adapter: Any, max_retries: int = 2) -> None:
		self.main_adapter = main_adapter
		self.max_retries = max_retries
		# Disable ChatAdapter -> JSONAdapter implicit fallback.
		# It sends contradictory XML-in-JSON prompts and wastes an LLM call.
		if hasattr(main_adapter, "use_json_adapter_fallback"):
			main_adapter.use_json_adapter_fallback = False

	def __call__(
		self,
		lm: Any,
		lm_kwargs: dict[str, Any],
		signature: type,
		demos: list[dict[str, Any]],
		inputs: dict[str, Any],
	) -> list[dict[str, Any]]:
		"""Call the main adapter with retry on parse failure."""
		# First attempt — normal call through the main adapter.
		try:
			return self.main_adapter(lm, lm_kwargs, signature, demos, inputs)
		except AdapterParseError as first_error:
			logger.info(
				"RetryAdapter: initial parse failed, retrying with error feedback "
				"(%d retries available)",
				self.max_retries,
			)
			last_error: AdapterParseError = first_error

		# Build retry signature with error-feedback fields.
		retry_signature = _add_retry_fields(signature)
		retry_inputs = {**inputs}
		retry_inputs["previous_response"] = last_error.lm_response or ""
		retry_inputs["error_message"] = str(last_error)

		for attempt in range(1, self.max_retries + 1):
			try:
				return self.main_adapter(
					lm, lm_kwargs, retry_signature, demos, retry_inputs,
				)
			except AdapterParseError as exc:
				logger.warning(
					"RetryAdapter: retry %d/%d failed: %s",
					attempt,
					self.max_retries,
					str(exc)[:120],
				)
				last_error = exc
				retry_inputs["previous_response"] = exc.lm_response or ""
				retry_inputs["error_message"] = str(exc)

		raise last_error

	def __getattr__(self, name: str) -> Any:
		"""Delegate all other attribute access to the main adapter."""
		return getattr(self.main_adapter, name)
