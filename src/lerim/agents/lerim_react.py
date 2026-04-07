"""LerimReact: dspy.ReAct clone using native function calling.

This module is a near-verbatim copy of dspy.predict.react.ReAct (version pinned
in lerim-cli's venv), with two minimal changes to enable native function calling:

1. The react_signature uses `available_tools: list[dspy.Tool]` input and
   `next_tool_call: dspy.ToolCalls` output instead of `next_tool_name: Literal[...]`
   and `next_tool_args: dict[str, Any]`. This triggers DSPy's ChatAdapter to route
   tool selection through the LLM API's native function calling channel.

2. The forward loop extracts tool name and args from `pred.next_tool_call.tool_calls[0]`
   instead of `pred.next_tool_name` and `pred.next_tool_args`.

Everything else (instruction text, trajectory keys, truncation, async path,
fallback extraction) is identical to dspy.ReAct so existing tooling that inspects
trajectories (diagnostics, eval behavior checks, optimizers) keeps working.

Why this exists: dspy.ReAct's text-based tool calling produces frequent
AdapterParseError with MiniMax M2.5, GLM, and other non-OpenAI models that
don't reliably follow the [[ ## next_tool_name ## ]] text format. See GitHub
issues stanfordnlp/dspy#8364, #8377.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from litellm import ContextWindowExceededError

import dspy
from dspy.adapters.types.tool import Tool
from dspy.primitives.module import Module
from dspy.signatures.signature import ensure_signature

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
	from dspy.signatures.signature import Signature


class LerimReact(Module):
	"""ReAct agent using native function calling via dspy.ToolCalls.

	Drop-in replacement for dspy.ReAct with the same constructor signature,
	same forward return shape, and same trajectory key format.
	"""

	def __init__(self, signature: type["Signature"], tools: list[Callable], max_iters: int = 20):
		"""
		ReAct stands for "Reasoning and Acting," a popular paradigm for building tool-using agents.
		In this approach, the language model is iteratively provided with a list of tools and has
		to reason about the current situation. The model decides whether to call a tool to gather more
		information or to finish the task based on its reasoning process. The DSPy version of ReAct is
		generalized to work over any signature, thanks to signature polymorphism.

		This LerimReact variant uses native function calling (dspy.ToolCalls output) instead of the
		text-based approach used by dspy.ReAct, making it robust against models that don't reliably
		follow the [[ ## next_tool_name ## ]] text format.

		Args:
			signature: The signature of the module, which defines the input and output of the react module.
			tools (list[Callable]): A list of functions, callable objects, or `dspy.Tool` instances.
			max_iters (Optional[int]): The maximum number of iterations to run. Defaults to 20.
		"""
		super().__init__()
		self.signature = signature = ensure_signature(signature)
		self.max_iters = max_iters

		tools = [t if isinstance(t, Tool) else Tool(t) for t in tools]
		tools = {tool.name: tool for tool in tools}

		inputs = ", ".join([f"`{k}`" for k in signature.input_fields.keys()])
		outputs = ", ".join([f"`{k}`" for k in signature.output_fields.keys()])
		instr = [f"{signature.instructions}\n"] if signature.instructions else []

		instr.extend(
			[
				f"You are an Agent. In each episode, you will be given the fields {inputs} as input. And you can see your past trajectory so far.",
				f"Your goal is to use one or more of the supplied tools to collect any necessary information for producing {outputs}.\n",
				"At each turn you will call exactly one tool from the `available_tools` list to make progress.",
				"After each tool call, you receive a resulting observation, which gets appended to your trajectory.\n",
				"When selecting the next_tool_call, the tool must be one of:\n",
			]
		)

		tools["finish"] = Tool(
			func=lambda: "Completed.",
			name="finish",
			desc=f"Marks the task as complete. That is, signals that all information for producing the outputs, i.e. {outputs}, are now available to be extracted.",
			args={},
		)

		for idx, tool in enumerate(tools.values()):
			instr.append(f"({idx + 1}) {tool}")
		instr.append("When providing `next_tool_call`, use the native function calling interface to call exactly one tool.")

		react_signature = (
			dspy.Signature({**signature.input_fields}, "\n".join(instr))
			.append("trajectory", dspy.InputField(), type_=str)
			.append("available_tools", dspy.InputField(), type_=list[dspy.Tool])
			.append("next_tool_call", dspy.OutputField(), type_=dspy.ToolCalls)
		)

		fallback_signature = dspy.Signature(
			{**signature.input_fields, **signature.output_fields},
			signature.instructions,
		).append("trajectory", dspy.InputField(), type_=str)

		self.tools = tools
		self.react = dspy.Predict(react_signature)
		self.extract = dspy.ChainOfThought(fallback_signature)

	def _format_trajectory(self, trajectory: dict[str, Any]):
		"""Format the trajectory dict into a string using the active adapter."""
		adapter = dspy.settings.adapter or dspy.ChatAdapter()
		trajectory_signature = dspy.Signature(f"{', '.join(trajectory.keys())} -> x")
		return adapter.format_user_message_content(trajectory_signature, trajectory)

	def forward(self, **input_args):
		"""Run the ReAct loop until `finish` is called or `max_iters` is reached."""
		trajectory = {}
		max_iters = input_args.pop("max_iters", self.max_iters)
		for idx in range(max_iters):
			try:
				pred = self._call_with_potential_trajectory_truncation(
					self.react,
					trajectory,
					available_tools=list(self.tools.values()),
					**input_args,
				)
			except ValueError as err:
				logger.warning(f"Ending the trajectory: Agent failed to select a valid tool: {_fmt_exc(err)}")
				break

			if not pred.next_tool_call or not pred.next_tool_call.tool_calls:
				logger.warning(f"Ending the trajectory: Agent returned no tool call at iteration {idx}")
				break

			tool_call = pred.next_tool_call.tool_calls[0]
			tool_name = tool_call.name
			tool_args = tool_call.args or {}

			trajectory[f"tool_name_{idx}"] = tool_name
			trajectory[f"tool_args_{idx}"] = tool_args

			try:
				trajectory[f"observation_{idx}"] = self.tools[tool_name](**tool_args)
			except Exception as err:
				trajectory[f"observation_{idx}"] = f"Execution error in {tool_name}: {_fmt_exc(err)}"

			if tool_name == "finish":
				break

		extract = self._call_with_potential_trajectory_truncation(self.extract, trajectory, **input_args)
		return dspy.Prediction(trajectory=trajectory, **extract)

	async def aforward(self, **input_args):
		"""Async variant of `forward`."""
		trajectory = {}
		max_iters = input_args.pop("max_iters", self.max_iters)
		for idx in range(max_iters):
			try:
				pred = await self._async_call_with_potential_trajectory_truncation(
					self.react,
					trajectory,
					available_tools=list(self.tools.values()),
					**input_args,
				)
			except ValueError as err:
				logger.warning(f"Ending the trajectory: Agent failed to select a valid tool: {_fmt_exc(err)}")
				break

			if not pred.next_tool_call or not pred.next_tool_call.tool_calls:
				logger.warning(f"Ending the trajectory: Agent returned no tool call at iteration {idx}")
				break

			tool_call = pred.next_tool_call.tool_calls[0]
			tool_name = tool_call.name
			tool_args = tool_call.args or {}

			trajectory[f"tool_name_{idx}"] = tool_name
			trajectory[f"tool_args_{idx}"] = tool_args

			try:
				trajectory[f"observation_{idx}"] = await self.tools[tool_name].acall(**tool_args)
			except Exception as err:
				trajectory[f"observation_{idx}"] = f"Execution error in {tool_name}: {_fmt_exc(err)}"

			if tool_name == "finish":
				break

		extract = await self._async_call_with_potential_trajectory_truncation(self.extract, trajectory, **input_args)
		return dspy.Prediction(trajectory=trajectory, **extract)

	def _call_with_potential_trajectory_truncation(self, module, trajectory, **input_args):
		"""Invoke `module` with the formatted trajectory, truncating on context overflow."""
		for _ in range(3):
			try:
				return module(
					**input_args,
					trajectory=self._format_trajectory(trajectory),
				)
			except ContextWindowExceededError:
				logger.warning("Trajectory exceeded the context window, truncating the oldest tool call information.")
				trajectory = self.truncate_trajectory(trajectory)
		raise ValueError("The context window was exceeded even after 3 attempts to truncate the trajectory.")

	async def _async_call_with_potential_trajectory_truncation(self, module, trajectory, **input_args):
		"""Async variant of `_call_with_potential_trajectory_truncation`."""
		for _ in range(3):
			try:
				return await module.acall(
					**input_args,
					trajectory=self._format_trajectory(trajectory),
				)
			except ContextWindowExceededError:
				logger.warning("Trajectory exceeded the context window, truncating the oldest tool call information.")
				trajectory = self.truncate_trajectory(trajectory)
		raise ValueError("The context window was exceeded even after 3 attempts to truncate the trajectory.")

	def truncate_trajectory(self, trajectory):
		"""Truncates the trajectory so that it fits in the context window.

		Users can override this method to implement their own truncation logic.
		"""
		keys = list(trajectory.keys())
		if len(keys) < 3:
			# Every tool call has 3 keys: tool_name, tool_args, and observation.
			raise ValueError(
				"The trajectory is too long so your prompt exceeded the context window, but the trajectory cannot be "
				"truncated because it only has one tool call."
			)

		for key in keys[:3]:
			trajectory.pop(key)

		return trajectory


def _fmt_exc(err: BaseException, *, limit: int = 5) -> str:
	"""
	Return a one-string traceback summary.
	* `limit` - how many stack frames to keep (from the innermost outwards).
	"""

	import traceback

	return "\n" + "".join(traceback.format_exception(type(err), err, err.__traceback__, limit=limit)).strip()
