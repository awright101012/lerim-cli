"""Unit tests for write_summary tool."""

from __future__ import annotations

import json

import frontmatter

from lerim.agents.tools import write_summary
from tests.helpers import make_config


def _make_ctx(tmp_path):
	"""Build a minimal RuntimeContext for testing write_summary."""
	from lerim.agents.context import RuntimeContext

	memory_root = tmp_path / "memory"
	memory_root.mkdir()
	run_folder = tmp_path / "workspace" / "sync-test-001"
	run_folder.mkdir(parents=True)
	summary_artifact = run_folder / "summary.json"

	return RuntimeContext(
		config=make_config(tmp_path),
		repo_root=tmp_path,
		memory_root=memory_root,
		workspace_root=tmp_path / "workspace",
		run_folder=run_folder,
		extra_read_roots=(),
		run_id="sync-test-001",
		artifact_paths={"summary": summary_artifact},
	)


def test_write_summary_creates_file(tmp_path):
	"""write_summary creates a markdown file in summaries/ subdirectory."""
	ctx = _make_ctx(tmp_path)
	result = json.loads(write_summary(
		ctx,
		title="Auth setup session",
		description="Set up JWT auth with HS256.",
		user_intent="Configure authentication for the API.",
		session_narrative="Decided on JWT with HS256, configured middleware.",
		tags="auth,jwt",
	))
	from pathlib import Path
	path = Path(result["summary_path"])
	assert path.exists()
	assert "summaries" in str(path)
	assert path.suffix == ".md"


def test_write_summary_frontmatter(tmp_path):
	"""Written summary has correct frontmatter fields."""
	ctx = _make_ctx(tmp_path)
	result = json.loads(write_summary(
		ctx,
		title="Debug logging fix",
		description="Fixed excessive debug logging.",
		user_intent="Reduce log noise in production.",
		session_narrative="Identified verbose logger, set level to WARNING.",
	))
	from pathlib import Path
	path = Path(result["summary_path"])
	parsed = frontmatter.load(str(path))
	assert parsed["title"] == "Debug logging fix"
	assert parsed["description"] == "Fixed excessive debug logging."
	assert parsed["source"] == "sync-test-001"
	assert "## User Intent" in parsed.content
	assert "## What Happened" in parsed.content


def test_write_summary_writes_artifact(tmp_path):
	"""write_summary also writes summary.json artifact for runtime."""
	ctx = _make_ctx(tmp_path)
	write_summary(
		ctx,
		title="Test session",
		description="A test.",
		user_intent="Testing.",
		session_narrative="Ran tests.",
	)
	artifact = ctx.artifact_paths["summary"]
	assert artifact.exists()
	data = json.loads(artifact.read_text(encoding="utf-8"))
	assert data["summary_path"]


def test_write_summary_rejects_empty_title(tmp_path):
	"""write_summary returns ERROR for empty title."""
	ctx = _make_ctx(tmp_path)
	result = write_summary(ctx, title="", description="d", user_intent="u", session_narrative="s")
	assert result.startswith("ERROR")


def test_write_summary_tags_parsing(tmp_path):
	"""Tags are parsed from comma-separated string."""
	ctx = _make_ctx(tmp_path)
	result = json.loads(write_summary(
		ctx,
		title="Tag test",
		description="Testing tags.",
		user_intent="Test tag parsing.",
		session_narrative="Verified tags work.",
		tags="  auth , jwt , security ",
	))
	from pathlib import Path
	parsed = frontmatter.load(str(Path(result["summary_path"])))
	assert parsed["tags"] == ["auth", "jwt", "security"]
