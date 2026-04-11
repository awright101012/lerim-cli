"""PydanticAI ExtractAgent — single-pass baseline used for A/B benchmark.

Same prompt, tools, and task as the three-pass pipeline in `extract.py`, but
runs in a single agent loop. Retained as a baseline so the eval harness can
compare single-pass vs three-pass on the same dataset.

Shares the six standalone tool functions (`read`, `grep`, `scan`, `write`,
`edit`, `verify_index`) and the `ExtractDeps` dataclass from
`lerim.agents.tools` — one function per tool, zero wrappers. The only things
local to this file are:

- `SYSTEM_PROMPT` — the combined single-pass prompt
- `ExtractionResult` — the single-pass output type
- `build_extract_agent` — constructs a PydanticAI Agent with all 6 tools
- `build_model` — canonical OpenAI-compatible model builder (used by both variants)
- `run_extraction` — the single-pass runner matching `run_extraction_three_pass`
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from lerim.agents.tools import (
	ExtractDeps,
	edit,
	grep,
	read,
	scan,
	verify_index,
	write,
)


# -- System prompt (verbatim copy of ExtractSignature docstring) -----------

SYSTEM_PROMPT = """\
You are the Lerim memory extraction agent. You read coding-agent session
traces and write durable memory files for future sessions.

Read the session trace, identify what is worth remembering, deduplicate
against existing memories, write new memory files, update the index, and
write a session summary.

Memory files are named {type}_{topic}.md (e.g. feedback_use_tabs.md,
project_dspy_migration.md). The type is encoded in the filename.
Each file has YAML frontmatter (name, description, type) and a markdown body.

Body format for feedback/project memories -- use inline bold, NOT ## headings:
  State the rule or decision first (one line).
  **Why:** reason it matters.
  **How to apply:** concrete action for future sessions.
Example:
  Use tabs for indentation in all code files.
  **Why:** team convention; spaces were rejected in code review.
  **How to apply:** set indent_style=tab; flag spaces in PRs.
DO NOT use ## headings inside the body -- headings are only for summaries.

Project memories must lead with the fact or decision, not narrate what happened.
Bad: "## What Happened\\nWe decided to use Redis..." -- this is summary style.
Good: "Redis chosen as cache layer (replaced Memcached).\\n**Why:** ..."

CRITICAL RULE: If the user explicitly asks to remember, memorize, store, or "keep in mind"
something, you MUST call write() for that content (usually type user or
feedback) or if exists, edit(). This overrides all skip rules below.
Do not treat explicit requests as debugging or ephemeral.

Duplicates are worse than gaps -- skip when uncertain.
An empty session (no memories written) is valid only when nothing in
the critical rules applies and there is no durable signal in the trace.

EXTRACTION CRITERIA:
- Extract: user role, goals, preferences, working style (about the person)
- Extract: feedback corrections ("don't do X") AND confirmations ("yes, exactly")
- Extract: project decisions, context, constraints NOT in code or git
- Extract: reference pointers to external systems (dashboards, Linear projects, etc.)
- Do NOT extract: Code patterns, architecture, file paths, function names, module names
- Do NOT extract: Git history, recent changes
- Do NOT extract: Debugging solutions
- Do NOT extract: Anything in CLAUDE.md or README
- Do NOT extract: Ephemeral task details, in-progress work
- Do NOT extract: Generic programming knowledge everyone knows

STEPS:
1. ORIENT: Start by calling scan() to see existing memories, then read("index.md") for
   current organization, then read("trace", offset=0, limit=100) to read the FIRST chunk.
   Use grep("trace", "remember") for explicit user requests across the whole trace.

2. CHUNKED READ: read("trace") is hard-capped at 100 lines per call.
   Page through by incrementing offset by 100 each call:
     read("trace", offset=0, limit=100) -> lines 1-100
     read("trace", offset=100, limit=100) -> lines 101-200
   Continue until header says Y == total lines.
   NEVER re-read the same chunk. After reading each chunk, extract and write before moving on.

3. ANALYZE: Identify extractable items from each chunk using the criteria above.

4. DEDUP: Compare each candidate against existing memories from scan.
   Same topic? Skip. Related but new info? read() then edit(). No match? write().

5. WRITE: For each new memory call write(type, name, description, body).
   To update existing, use read() then edit().

6. INDEX: Call verify_index() to check index.md matches files.
   If NOT OK, edit("index.md", ...) to fix.

7. SUMMARIZE: Write a session summary:
   write(type="summary", name="Short title", description="One-line summary",
              body="## User Intent\\n...\\n\\n## What Happened\\n...")

Complete ALL applicable steps before finishing.
If the trace has extractable content, you MUST write at least one memory
AND a summary AND verify the index."""


class ExtractionResult(BaseModel):
	"""Structured output from the extraction agent."""
	completion_summary: str = Field(description="Short plain-text completion summary")


def build_extract_agent(model: OpenAIChatModel) -> Agent[ExtractDeps, ExtractionResult]:
	"""Build a PydanticAI agent with the same 6 tools as the three-pass pipeline.

	Uses the shared standalone tool functions from `extract.py` so any benchmark
	comparison between single-pass and three-pass isolates the architectural
	difference (one pass vs three), not tool wiring differences.
	"""
	return Agent(
		model,
		deps_type=ExtractDeps,
		output_type=ExtractionResult,
		system_prompt=SYSTEM_PROMPT,
		tools=[read, grep, scan, write, edit, verify_index],
		output_retries=3,
	)


def build_model(provider_name: str = "minimax", model_name: str = "MiniMax-M2.5") -> OpenAIChatModel:
	"""Build an OpenAI-compatible model for PydanticAI.

	Supports minimax and zai providers via their OpenAI-compatible endpoints.
	"""
	configs = {
		"minimax": {
			"base_url": "https://api.minimax.io/v1",
			"env_var": "MINIMAX_API_KEY",
		},
		"zai": {
			"base_url": "https://api.z.ai/api/coding/paas/v4",
			"env_var": "ZAI_API_KEY",
		},
		"ollama": {
			"base_url": "http://localhost:11434/v1",
			"env_var": None,
		},
	}
	cfg = configs.get(provider_name)
	if not cfg:
		raise ValueError(f"Unknown provider: {provider_name}")

	api_key = "ollama" if provider_name == "ollama" else os.environ.get(cfg["env_var"])
	if not api_key:
		raise RuntimeError(f"{cfg['env_var']} required for provider={provider_name}")

	provider = OpenAIProvider(base_url=cfg["base_url"], api_key=api_key)
	return OpenAIChatModel(model_name, provider=provider)


def run_extraction(
	memory_root: Path,
	trace_path: Path,
	model: OpenAIChatModel,
	run_folder: Path | None = None,
	return_messages: bool = False,
):
	"""Run the single-pass PydanticAI extract agent and return the result.

	Args:
		memory_root: Directory containing memory files, index.md, and summaries/.
		trace_path: Path to the session trace .jsonl file.
		model: PydanticAI OpenAIChatModel (built by `build_model()`).
		run_folder: Optional run workspace folder for artifact output.
		return_messages: If True, return `(ExtractionResult, list[ModelMessage])`.
			Default False for backward compatibility.

	Returns:
		ExtractionResult, or a `(ExtractionResult, list)` tuple if return_messages=True.
	"""
	agent = build_extract_agent(model)
	deps = ExtractDeps(
		memory_root=memory_root,
		trace_path=trace_path,
		run_folder=run_folder,
	)
	result = agent.run_sync("Extract memories from the session trace.", deps=deps)
	if return_messages:
		return result.output, list(result.all_messages())
	return result.output


if __name__ == "__main__":
	"""Self-test: run the single-pass extractor on a fixture trace."""
	import sys
	import tempfile

	trace_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
		Path(__file__).parents[3] / "tests" / "fixtures" / "traces" / "claude_short.jsonl"
	)
	if not trace_path.exists():
		print(f"Error: trace not found: {trace_path}")
		sys.exit(1)

	with tempfile.TemporaryDirectory() as tmp:
		memory_root = Path(tmp) / "memory"
		memory_root.mkdir()
		(memory_root / "index.md").write_text("# Memory Index\n")
		(memory_root / "summaries").mkdir()

		print(f"Trace: {trace_path}")
		print(f"Memory root: {memory_root}")
		print()

		model = build_model()
		result = run_extraction(
			memory_root=memory_root,
			trace_path=trace_path,
			model=model,
		)

		print("=" * 60)
		print("RESULTS")
		print("=" * 60)
		print(f"Completion summary: {result.completion_summary}")
		print()

		memories = [f for f in memory_root.glob("*.md") if f.name != "index.md"]
		print(f"Memories written: {len(memories)}")
		for m in memories:
			print(f"  {m.name}")
		print()

		summaries = list((memory_root / "summaries").glob("*.md"))
		print(f"Summaries written: {len(summaries)}")
		for s in summaries:
			print(f"  {s.name}")
		print()

		index = memory_root / "index.md"
		print(f"Index content:\n{index.read_text()}")
