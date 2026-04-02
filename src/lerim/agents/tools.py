"""DSPy ReAct tools for lerim agent runs.

Each function takes RuntimeContext as its first parameter.
Bind with functools.partial(fn, ctx) before passing to dspy.ReAct.

Memory types follow Claude Code's 4-type taxonomy:
- user: role, goals, preferences, knowledge
- feedback: corrections AND confirmations of approach
- project: ongoing work context not derivable from code/git
- reference: pointers to external systems

All memories are stored flat under memory_root (no subdirectories by type).

Tools:
- write_memory: structured memory creation with 4-type taxonomy
- write_report: write a JSON report file to the workspace
- read_file: read a file from within allowed directories
- list_files: list files matching a glob pattern
- archive_memory: move a memory file to archived/
- edit_memory: replace a memory file's content
- scan_memory_manifest: scan all memory files and return a compact manifest
- update_memory_index: write MEMORY.md index file
"""

from __future__ import annotations

import inspect
import json
import shutil
from functools import wraps
from pathlib import Path
from typing import Callable

from lerim.agents.schemas import (
	MemoryRecord,
	canonical_memory_filename,
	slugify,
)
from lerim.agents.schemas import MEMORY_TYPES
from lerim.agents.context import RuntimeContext

from lerim.agents.contracts import is_within as _is_within


def write_memory(
	ctx: RuntimeContext,
	type: str,
	name: str,
	description: str,
	body: str,
) -> str:
	"""Create a memory file under memory_root (flat directory, no subfolders).

	Use this as the ONLY way to persist new memories. Call once per candidate
	classified as "add" or "update" in the classify step.

	Returns JSON: {"file_path": str, "bytes": int, "type": str}.

	Args:
		type: Memory type. One of: "user", "feedback", "project", "reference".
		name: Short descriptive title (max ~10 words). Used to generate the filename slug.
		description: One-line description for retrieval (~150 chars max).
		body: Memory content in plain text or markdown. Minimum 2 sentences.
	"""
	if not ctx.memory_root:
		return "ERROR: memory_root is not set in runtime context."

	if type not in MEMORY_TYPES:
		return (
			f"ERROR: Invalid type='{type}'. "
			f"Must be one of: {', '.join(MEMORY_TYPES)}. "
			"Example: write_memory(type='feedback', name='...', description='...', body='...')"
		)

	if not name or not name.strip():
		return (
			"ERROR: name cannot be empty. Provide a short descriptive title. "
			"Example: 'Never commit without asking'"
		)

	if not description or not description.strip():
		return (
			"ERROR: description cannot be empty. Provide a one-line description for retrieval. "
			"Example: 'Got burned by auto-commits; always show changes first'"
		)

	if not body or not body.strip():
		return (
			"ERROR: body cannot be empty. Provide memory content (minimum 2 sentences). "
			"Example: 'Never commit without explicit user confirmation. "
			"**Why:** Previous auto-commit overwrote in-progress work.'"
		)

	try:
		record = MemoryRecord(
			type=type,
			name=name.strip(),
			description=description.strip(),
			body=body.strip(),
			id=slugify(name),
			source=ctx.run_id,
		)
	except Exception as exc:
		return (
			f"ERROR: Invalid memory fields: {exc}. "
			f"Required: type (one of {', '.join(MEMORY_TYPES)}), "
			"name (non-empty string), description (non-empty string), body (non-empty string)."
		)

	filename = canonical_memory_filename(title=name, run_id=ctx.run_id)
	target = ctx.memory_root / filename

	content = record.to_markdown()
	target.parent.mkdir(parents=True, exist_ok=True)
	target.write_text(content, encoding="utf-8")

	return json.dumps({
		"file_path": str(target),
		"bytes": len(content.encode("utf-8")),
		"type": type,
	})


def write_summary(
	ctx: RuntimeContext,
	title: str,
	description: str,
	user_intent: str,
	session_narrative: str,
	tags: str = "",
) -> str:
	"""Write a session summary markdown to memory_root/summaries/YYYYMMDD/HHMMSS/{slug}.md.

	Call this after reading and analyzing the session trace. Produce a concise summary
	capturing the user's goal, what happened, and the outcome.

	Returns JSON: {"summary_path": str, "bytes": int}.

	Args:
		title: Short session title (max 10 words).
		description: One-line description of what the session achieved.
		user_intent: The user's overall goal for this session (at most 150 words).
		session_narrative: Chronological narrative of what happened (at most 200 words).
		tags: Comma-separated topic tags for the summary.
	"""
	import frontmatter as fm_lib
	from datetime import datetime, timezone

	if not ctx.memory_root:
		return "ERROR: memory_root is not set in runtime context."

	if not title or not title.strip():
		return "ERROR: title cannot be empty."
	if not user_intent or not user_intent.strip():
		return "ERROR: user_intent cannot be empty."
	if not session_narrative or not session_narrative.strip():
		return "ERROR: session_narrative cannot be empty."

	now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
	slug = slugify(title)
	date_compact = datetime.now(timezone.utc).strftime("%Y%m%d")
	time_compact = datetime.now(timezone.utc).strftime("%H%M%S")

	summaries_dir = ctx.memory_root / "summaries" / date_compact / time_compact
	summaries_dir.mkdir(parents=True, exist_ok=True)
	summary_path = summaries_dir / f"{slug}.md"

	tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

	fm_dict = {
		"id": slug,
		"title": title.strip(),
		"created": now_iso,
		"source": ctx.run_id,
		"description": description.strip(),
		"tags": tag_list,
	}

	body = f"## User Intent\n\n{user_intent.strip()}\n\n## What Happened\n\n{session_narrative.strip()}"

	post = fm_lib.Post(body, **fm_dict)
	summary_path.write_text(fm_lib.dumps(post) + "\n", encoding="utf-8")

	# Write summary artifact so runtime.py can find the summary_path
	if ctx.artifact_paths and "summary" in ctx.artifact_paths:
		artifact = ctx.artifact_paths["summary"]
		artifact.parent.mkdir(parents=True, exist_ok=True)
		artifact.write_text(
			json.dumps({"summary_path": str(summary_path)}, indent=2) + "\n",
			encoding="utf-8",
		)

	return json.dumps({
		"summary_path": str(summary_path),
		"bytes": len(summary_path.read_text(encoding="utf-8").encode("utf-8")),
	})


def write_report(
	ctx: RuntimeContext,
	file_path: str,
	content: str,
) -> str:
	"""Write a JSON report file to the run workspace folder.

	Use this as the final step to persist the run report. Content MUST be
	valid JSON. Path MUST be inside the run workspace.

	Returns a confirmation string on success or "Error: ..." on failure.

	Args:
		file_path: Absolute path within run_folder to write to.
		content: Valid JSON string. Invalid JSON is rejected.
	"""
	resolved = Path(file_path).resolve()
	run_folder = ctx.run_folder
	if not run_folder:
		return "Error: run_folder is not set in runtime context"
	if not _is_within(resolved, run_folder):
		return f"Error: path {file_path} is outside the workspace {run_folder}"
	try:
		json.loads(content)
	except json.JSONDecodeError:
		return "Error: content is not valid JSON"
	resolved.parent.mkdir(parents=True, exist_ok=True)
	resolved.write_text(content, encoding="utf-8")
	return f"Report written to {file_path}"


def read_file(
	ctx: RuntimeContext,
	file_path: str,
) -> str:
	"""Read a file's full text content. Only files under memory_root, run_folder, or extra_read_roots are allowed.

	Use this to inspect memory files, extract artifacts, or summaries in detail.

	Returns the file content as a string, or "Error: ..." on failure.

	Args:
		file_path: Absolute path to the file. Must be under memory_root, run_folder, or extra_read_roots.
	"""
	resolved = Path(file_path).resolve()
	allowed_roots: list[Path] = []
	if ctx.memory_root:
		allowed_roots.append(ctx.memory_root)
	if ctx.run_folder:
		allowed_roots.append(ctx.run_folder)
	for extra in (ctx.extra_read_roots or ()):
		allowed_roots.append(extra)
	if not any(_is_within(resolved, root) for root in allowed_roots):
		return f"Error: path {file_path} is outside allowed roots: {', '.join(str(r) for r in allowed_roots)}"
	if not resolved.exists():
		return f"Error: file not found: {file_path}"
	if not resolved.is_file():
		return f"Error: not a file: {file_path}"
	return resolved.read_text(encoding="utf-8")


def list_files(
	ctx: RuntimeContext,
	directory: str,
	pattern: str = "*.md",
) -> str:
	"""List file paths matching a glob pattern under memory_root, run_folder, or extra_read_roots.

	Use this to discover memory files or artifacts before reading them.

	Returns a JSON array of absolute file paths, or "Error: ..." on failure.

	Args:
		directory: Absolute path to the directory to search in.
		pattern: Glob pattern to filter files. Default "*.md".
	"""
	resolved = Path(directory).resolve()
	allowed_roots: list[Path] = []
	if ctx.memory_root:
		allowed_roots.append(ctx.memory_root)
	if ctx.run_folder:
		allowed_roots.append(ctx.run_folder)
	for extra in (ctx.extra_read_roots or ()):
		allowed_roots.append(extra)
	if not any(_is_within(resolved, root) for root in allowed_roots):
		return f"Error: directory {directory} is outside allowed roots: {', '.join(str(r) for r in allowed_roots)}"
	if not resolved.exists():
		return "[]"
	if not resolved.is_dir():
		return f"Error: not a directory: {directory}"
	files = sorted(str(f) for f in resolved.glob(pattern))
	return json.dumps(files)


def archive_memory(
	ctx: RuntimeContext,
	file_path: str,
) -> str:
	"""Soft-delete a memory by moving it to archived/ (e.g., foo.md -> archived/foo.md).

	Use this for low-value, superseded, or duplicate memories. Do NOT delete files directly.

	Returns JSON: {"archived": true, "source": str, "target": str}.

	Args:
		file_path: Absolute path to a .md memory file under memory_root.
	"""
	if not ctx.memory_root:
		return "ERROR: memory_root is not set in runtime context."

	resolved = Path(file_path).resolve()
	if not _is_within(resolved, ctx.memory_root):
		return f"ERROR: path {file_path} is outside memory_root {ctx.memory_root}"

	if not resolved.exists():
		return f"ERROR: file not found: {file_path}"

	if not resolved.is_file():
		return f"ERROR: not a file: {file_path}"

	if resolved.suffix != ".md":
		return f"ERROR: only .md files can be archived. Got: {resolved.name}"

	# Build archived target: memory_root/archived/{filename}
	target = ctx.memory_root / "archived" / resolved.name
	target.parent.mkdir(parents=True, exist_ok=True)
	shutil.move(str(resolved), str(target))

	return json.dumps({
		"archived": True,
		"source": str(resolved),
		"target": str(target),
	})


def edit_memory(
	ctx: RuntimeContext,
	file_path: str,
	new_content: str,
) -> str:
	"""Replace the full content of an existing memory file (frontmatter + body).

	Use this to merge content from duplicates or update memory fields.
	The file MUST already exist under memory_root.

	Returns JSON: {"edited": true, "file_path": str, "bytes": int}.

	Args:
		file_path: Absolute path to the memory file to overwrite.
		new_content: Complete replacement content. MUST start with "---" (YAML frontmatter).
	"""
	if not ctx.memory_root:
		return "ERROR: memory_root is not set in runtime context."

	resolved = Path(file_path).resolve()
	if not _is_within(resolved, ctx.memory_root):
		return f"ERROR: path {file_path} is outside memory_root {ctx.memory_root}"

	if not resolved.exists():
		return f"ERROR: file not found: {file_path}"

	if not resolved.is_file():
		return f"ERROR: not a file: {file_path}"

	# Validate new_content has YAML frontmatter
	stripped = new_content.strip()
	if not stripped.startswith("---"):
		return "ERROR: new_content must start with YAML frontmatter (---)"

	resolved.write_text(new_content, encoding="utf-8")

	return json.dumps({
		"edited": True,
		"file_path": str(resolved),
		"bytes": len(new_content.encode("utf-8")),
	})


def scan_memory_manifest(ctx: RuntimeContext) -> str:
	"""Scan all memory files and return a compact manifest.

	Returns a JSON list of {name, description, type, filename, age} for each .md file
	in the memory root (excluding MEMORY.md, summaries/, archived/).
	"""
	import frontmatter as fm_lib

	from lerim.agents.schemas import staleness_note

	memory_root = ctx.memory_root
	if not memory_root or not Path(memory_root).is_dir():
		return json.dumps({"error": "memory_root not set or missing"})

	root = Path(memory_root)
	manifest = []
	for md_file in sorted(root.glob("*.md")):
		if md_file.name == "MEMORY.md":
			continue
		try:
			post = fm_lib.load(str(md_file))
			manifest.append({
				"name": post.get("name", md_file.stem),
				"description": post.get("description", ""),
				"type": post.get("type", "project"),
				"filename": md_file.name,
				"age": staleness_note(post.get("created", "")),
			})
		except Exception:
			manifest.append({
				"name": md_file.stem,
				"filename": md_file.name,
				"type": "unknown",
				"description": "",
				"age": "",
			})

	return json.dumps({"count": len(manifest), "memories": manifest}, indent=2)


def update_memory_index(content: str, ctx: RuntimeContext) -> str:
	"""Write MEMORY.md index file. Content should be one line per memory, max 200 lines.

	Format: `- [Title](filename.md) -- one-line description`

	Args:
		content: The full text content for MEMORY.md.
	"""
	memory_root = ctx.memory_root
	if not memory_root:
		return json.dumps({"error": "memory_root not set"})

	root = Path(memory_root)
	index_path = root / "MEMORY.md"

	# Enforce 200-line / 25KB cap
	lines = content.strip().splitlines()
	if len(lines) > 200:
		lines = lines[:200]
		lines.append("> WARNING: Truncated to 200 lines. Move detail into topic files.")

	final = "\n".join(lines) + "\n"
	if len(final.encode("utf-8")) > 25_000:
		# Truncate by bytes
		final = final.encode("utf-8")[:25_000].decode("utf-8", errors="ignore")
		final += "\n> WARNING: Truncated to 25KB. Shorten entries.\n"

	index_path.write_text(final, encoding="utf-8")
	return json.dumps({"file_path": str(index_path), "bytes": len(final), "lines": len(final.splitlines())})


# ---------------------------------------------------------------------------
# Tool binding -- produce ctx-bound callables with preserved signatures
# ---------------------------------------------------------------------------

def _bind_tool(fn: Callable, ctx: RuntimeContext) -> Callable:
	"""Bind ctx to a tool function, preserving __name__, __doc__, and signature.

	functools.partial loses the original signature -- dspy.Tool sees
	(*args, **kwargs) and name='partial'. This wrapper creates a proper
	function with the ctx parameter removed from the signature so
	dspy.Tool can introspect parameter names, types, and descriptions.
	"""
	sig = inspect.signature(fn)
	params = [p for k, p in sig.parameters.items() if k != "ctx"]
	new_sig = sig.replace(parameters=params)

	@wraps(fn)
	def wrapper(*args, **kwargs):
		return fn(ctx, *args, **kwargs)

	wrapper.__signature__ = new_sig  # type: ignore[attr-defined]
	return wrapper


def bind_extract_tools(ctx: RuntimeContext) -> list[Callable]:
	"""Build the tool list for the extract flow, bound to ctx."""
	return [
		_bind_tool(read_file, ctx),
		_bind_tool(scan_memory_manifest, ctx),
		_bind_tool(write_memory, ctx),
		_bind_tool(write_summary, ctx),
		_bind_tool(edit_memory, ctx),
		_bind_tool(update_memory_index, ctx),
		_bind_tool(list_files, ctx),
		_bind_tool(write_report, ctx),
	]


def bind_maintain_tools(ctx: RuntimeContext) -> list[Callable]:
	"""Build the tool list for the maintain flow, bound to ctx."""
	return [
		_bind_tool(write_memory, ctx),
		_bind_tool(write_report, ctx),
		_bind_tool(read_file, ctx),
		_bind_tool(list_files, ctx),
		_bind_tool(archive_memory, ctx),
		_bind_tool(edit_memory, ctx),
		_bind_tool(scan_memory_manifest, ctx),
		_bind_tool(update_memory_index, ctx),
	]


def bind_ask_tools(ctx: RuntimeContext) -> list[Callable]:
	"""Build the tool list for the ask flow, bound to ctx."""
	return [
		_bind_tool(scan_memory_manifest, ctx),
		_bind_tool(read_file, ctx),
		_bind_tool(list_files, ctx),
	]
