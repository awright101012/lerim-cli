"""Unit tests for the three-pass PydanticAI extraction pipeline.

Pure Python, no LLM calls. Tests the schemas, tool function signatures, agent
builders, system prompts, and usage limits defined in
`src/lerim/agents/extract.py` and the shared tool functions in
`src/lerim/agents/tools.py`. End-to-end behavior is covered by the self-test
in `extract.py.__main__` and by the integration suite.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import UsageLimits

from lerim.agents.extract import (
	EXTRACT_LIMITS,
	EXTRACT_SYSTEM_PROMPT,
	FINALIZE_LIMITS,
	FINALIZE_SYSTEM_PROMPT,
	REFLECT_LIMITS,
	REFLECT_SYSTEM_PROMPT,
	CandidateMemory,
	ChunkRef,
	ExtractResult,
	FinalizeResult,
	SessionUnderstanding,
	build_extract_agent,
	build_finalize_agent,
	build_reflect_agent,
)
from lerim.agents.tools import (
	ExtractDeps,
	edit,
	grep,
	read,
	scan,
	verify_index,
	write,
)


def test_extract_deps_schema():
	"""ExtractDeps has exactly 3 fields: memory_root, trace_path, run_folder.

	NO `tools` field — the class is path-only; tool functions access
	ctx.deps.memory_root directly.
	"""
	field_names = {f.name for f in fields(ExtractDeps)}
	assert field_names == {"memory_root", "trace_path", "run_folder"}
	assert "tools" not in field_names


def test_session_understanding_schema():
	"""SessionUnderstanding has user_goal, key_decisions, important_chunks,
	extractable_candidates, existing_memories_relevant. Nested ChunkRef has
	offset+topic; CandidateMemory has type+topic+evidence_offset.
	"""
	field_names = set(SessionUnderstanding.model_fields.keys())
	assert field_names == {
		"user_goal",
		"key_decisions",
		"important_chunks",
		"extractable_candidates",
		"existing_memories_relevant",
	}

	# Nested ChunkRef
	chunk_field_names = set(ChunkRef.model_fields.keys())
	assert chunk_field_names == {"offset", "topic"}

	# Nested CandidateMemory
	candidate_field_names = set(CandidateMemory.model_fields.keys())
	assert candidate_field_names == {"type", "topic", "evidence_offset"}

	# Constructable
	understanding = SessionUnderstanding(
		user_goal="Test goal",
		key_decisions=["decision 1"],
		important_chunks=[ChunkRef(offset=0, topic="intro")],
		extractable_candidates=[
			CandidateMemory(type="feedback", topic="prefer tabs", evidence_offset=42),
		],
		existing_memories_relevant=["feedback_tabs.md"],
	)
	assert understanding.user_goal == "Test goal"
	assert understanding.important_chunks[0].offset == 0
	assert understanding.extractable_candidates[0].evidence_offset == 42


def test_tool_functions_take_runcontext():
	"""All six tool functions must take RunContext[ExtractDeps] as their first
	positional arg (named `ctx`). This is what wires deps into the tool body
	via `ctx.deps.memory_root` / `ctx.deps.trace_path`.
	"""
	tool_functions = [read, grep, scan, write, edit, verify_index]
	for fn in tool_functions:
		sig = inspect.signature(fn)
		params = list(sig.parameters.values())
		assert len(params) >= 1, f"{fn.__name__} has no parameters"
		first = params[0]
		assert first.name == "ctx", (
			f"{fn.__name__} first param is {first.name!r}, expected 'ctx'"
		)
		# Annotation is stringified because of `from __future__ import annotations`.
		annotation_str = str(first.annotation)
		assert "RunContext" in annotation_str, (
			f"{fn.__name__} first param annotation is {annotation_str!r}, "
			f"expected to mention RunContext"
		)
		assert "ExtractDeps" in annotation_str, (
			f"{fn.__name__} first param annotation is {annotation_str!r}, "
			f"expected to mention ExtractDeps"
		)


def test_tool_functions_live_in_tools_module():
	"""Tool functions are defined in `lerim.agents.tools` — the single source
	of truth. `lerim.agents.extract` should only import them, never redefine.
	"""
	from lerim.agents import tools as tools_module
	from lerim.agents import extract as extract_module

	for name in ("read", "grep", "scan", "write", "edit", "verify_index"):
		assert hasattr(tools_module, name), f"tools.{name} is missing"
		# extract.py imports them so `hasattr` is True there too, but they
		# must be the SAME objects (i.e., no duplicate definitions).
		assert getattr(extract_module, name) is getattr(tools_module, name), (
			f"extract.{name} is not the same object as tools.{name} — "
			f"did you redefine the tool in extract.py?"
		)


def test_agent_builders_construct_without_error():
	"""All three agent builders construct with a TestModel and expose the
	expected output_type, so they're wired up correctly end-to-end.
	"""
	model = TestModel()

	reflect_agent = build_reflect_agent(model)
	extract_agent = build_extract_agent(model)
	finalize_agent = build_finalize_agent(model)

	assert reflect_agent.output_type is SessionUnderstanding
	assert extract_agent.output_type is ExtractResult
	assert finalize_agent.output_type is FinalizeResult


def test_reflect_prompt_contains_session_understanding():
	"""Pass 1 prompt must mention SessionUnderstanding as the output type
	and describe scanning existing memories, reading in chunks, and not writing.
	"""
	assert "SessionUnderstanding" in REFLECT_SYSTEM_PROMPT
	# Mentions the read-only tools by their new names
	assert "read(" in REFLECT_SYSTEM_PROMPT or "`read`" in REFLECT_SYSTEM_PROMPT or "read_" in REFLECT_SYSTEM_PROMPT
	assert "scan(" in REFLECT_SYSTEM_PROMPT or "`scan`" in REFLECT_SYSTEM_PROMPT or "scan_" in REFLECT_SYSTEM_PROMPT or "scan " in REFLECT_SYSTEM_PROMPT
	# Mentions chunked reading
	assert "chunk" in REFLECT_SYSTEM_PROMPT.lower() or "offset" in REFLECT_SYSTEM_PROMPT
	# Explicit no-write guard
	assert "DO NOT WRITE" in REFLECT_SYSTEM_PROMPT or "not write" in REFLECT_SYSTEM_PROMPT.lower()


def test_extract_prompt_contains_why_and_how():
	"""Pass 2 prompt must carry the body-format rules (inline bold **Why:** /
	**How to apply:**), the extraction criteria, and dedup guidance.
	"""
	assert "**Why:**" in EXTRACT_SYSTEM_PROMPT
	assert "**How to apply:**" in EXTRACT_SYSTEM_PROMPT
	assert "dedup" in EXTRACT_SYSTEM_PROMPT.lower() or "duplicate" in EXTRACT_SYSTEM_PROMPT.lower()
	# Extraction criteria markers (at least one)
	assert "Do NOT extract" in EXTRACT_SYSTEM_PROMPT
	# It should mention the key memory types
	assert "feedback" in EXTRACT_SYSTEM_PROMPT


def test_finalize_prompt_contains_verify_index():
	"""Pass 3 prompt must mention verify_index and the session summary
	headings it writes.
	"""
	assert "verify_index" in FINALIZE_SYSTEM_PROMPT
	assert "session summary" in FINALIZE_SYSTEM_PROMPT.lower()
	assert "## User Intent" in FINALIZE_SYSTEM_PROMPT
	assert "## What Happened" in FINALIZE_SYSTEM_PROMPT


def test_usage_limits_set():
	"""REFLECT_LIMITS, EXTRACT_LIMITS, FINALIZE_LIMITS are UsageLimits instances
	with request_limit set to a positive integer.
	"""
	for limits, name in [
		(REFLECT_LIMITS, "REFLECT_LIMITS"),
		(EXTRACT_LIMITS, "EXTRACT_LIMITS"),
		(FINALIZE_LIMITS, "FINALIZE_LIMITS"),
	]:
		assert isinstance(limits, UsageLimits), f"{name} is not a UsageLimits"
		assert limits.request_limit is not None, f"{name}.request_limit is None"
		assert limits.request_limit > 0, f"{name}.request_limit is not positive"
