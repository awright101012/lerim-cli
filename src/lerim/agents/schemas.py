"""Shared schemas for memory operations and on-disk record model.

This module contains Pydantic models used across multiple memory modules.
Memory types follow Claude Code's 4-type taxonomy:
- user: role, goals, preferences, knowledge
- feedback: corrections AND confirmations of approach
- project: ongoing work context not derivable from code/git
- reference: pointers to external systems

MemoryRecord subclasses MemoryCandidate (DSPy extraction schema) and adds
bookkeeping fields for persisted memory files.
All memories live in a flat directory — no subdirectories by type.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

import frontmatter
from pydantic import BaseModel, Field

MEMORY_TYPES = ("user", "feedback", "project", "reference")


class MemoryCandidate(BaseModel):
	"""One extracted memory candidate from a transcript."""

	type: Literal["user", "feedback", "project", "reference"] = Field(
		description="Memory type: user (role/preferences), feedback (corrections/confirmations), project (context not in code), reference (external pointers)."
	)
	name: str = Field(
		description="Short descriptive title. Start with verb or noun phrase. Max 10 words. Must identify the topic without reading the body."
	)
	description: str = Field(
		description="One-line description used for retrieval. Be specific — this decides relevance in future conversations. Max ~150 characters."
	)
	body: str = Field(
		description="Memory content. For feedback/project: lead with rule/fact, then **Why:** (rationale), then **How to apply:** (when this matters). Must be understandable without the original conversation. Minimum 2 sentences."
	)


class MemoryType(str, Enum):
	"""Canonical memory types."""

	user = "user"
	feedback = "feedback"
	project = "project"
	reference = "reference"
	summary = "summary"  # auto-generated session summaries (separate dir)


def slugify(value: str) -> str:
	"""Generate a filesystem-safe ASCII slug from text."""
	raw = (
		unicodedata.normalize("NFKD", str(value or ""))
		.encode("ascii", "ignore")
		.decode("ascii")
	)
	cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", raw.strip().lower()).strip("-")
	return cleaned or "memory"


def canonical_memory_filename(*, title: str, run_id: str) -> str:
	"""Build canonical filename: ``{YYYYMMDD}-{slug}.md``.

	Uses the date portion of run_id (format ``sync-YYYYMMDD-HHMMSS-hex``) when
	available, otherwise today's date.
	"""
	slug = slugify(title)
	parts = (run_id or "").split("-")
	date_str = next((p for p in parts if len(p) == 8 and p.isdigit()), None)
	if not date_str:
		date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
	return f"{date_str}-{slug}.md"


def staleness_note(mtime_iso: str) -> str:
	"""Return staleness caveat for memory age.

	Memories >7 days old get a verification warning.
	"""
	try:
		mtime = datetime.fromisoformat(mtime_iso)
		days = (datetime.now(timezone.utc) - mtime).days
	except (ValueError, TypeError):
		return ""
	if days == 0:
		return ""
	if days <= 7:
		return f"(saved {days} day{'s' if days != 1 else ''} ago)"
	return f"(saved {days} days ago — verify against current code before acting on this)"


class MemoryRecord(MemoryCandidate):
	"""On-disk memory record with bookkeeping fields.

	Subclasses MemoryCandidate (DSPy extraction schema) and adds
	id, created, updated, source for persistence.
	"""

	id: str
	created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
	updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
	source: str = ""

	def to_frontmatter_dict(self) -> dict:
		"""Build frontmatter payload: name, description, type + bookkeeping."""
		return {
			"name": self.name,
			"description": self.description,
			"type": self.type,
			"id": self.id,
			"created": self.created.isoformat(),
			"updated": self.updated.isoformat(),
			"source": self.source,
		}

	def to_markdown(self) -> str:
		"""Serialize record to frontmatter + body markdown format."""
		post = frontmatter.Post(self.body, **self.to_frontmatter_dict())
		return frontmatter.dumps(post) + "\n"


if __name__ == "__main__":
	"""Run a real-path self-test for MemoryRecord serialization."""
	record = MemoryRecord(
		id="20260331-queue-lifecycle",
		type="project",
		name="Queue lifecycle design",
		description="Keep queue states explicit for reliability",
		body="Keep queue states explicit. **Why:** Implicit state transitions caused lost jobs in production. **How to apply:** Always define state machine transitions in the catalog module.",
		source="self-test-run",
	)
	md = record.to_markdown()
	assert "---" in md
	assert "20260331-queue-lifecycle" in md
	assert "Queue lifecycle design" in md
	assert "Keep queue states explicit." in md

	fm_dict = record.to_frontmatter_dict()
	assert fm_dict["id"] == "20260331-queue-lifecycle"
	assert fm_dict["type"] == "project"
	assert fm_dict["name"] == "Queue lifecycle design"
	assert fm_dict["description"] == "Keep queue states explicit for reliability"
	assert "confidence" not in fm_dict
	assert "kind" not in fm_dict
	assert "tags" not in fm_dict

	# Verify slugify
	assert slugify("Hello World!") == "hello-world"
	assert slugify("") == "memory"
	assert slugify("  --test--  ") == "test"

	# Verify canonical_memory_filename
	fname = canonical_memory_filename(
		title="My Title",
		run_id="sync-20260220-120000-abc123",
	)
	assert fname == "20260220-my-title.md"

	# Verify staleness_note
	assert staleness_note(datetime.now(timezone.utc).isoformat()) == ""
	old = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
	note = staleness_note(old)
	assert "verify against current code" in note

	# Verify MemoryType values
	assert MemoryType.user.value == "user"
	assert MemoryType.feedback.value == "feedback"
	assert MemoryType.project.value == "project"
	assert MemoryType.reference.value == "reference"

	# Verify MemoryCandidate schema
	candidate = MemoryCandidate(
		type="feedback",
		name="Never commit without asking",
		description="Got burned by auto-commits; always show changes first",
		body="Never commit without explicit user confirmation. **Why:** Previous auto-commit overwrote in-progress work. **How to apply:** Show diff and ask before any git commit.",
	)
	assert set(MemoryCandidate.model_fields.keys()) == {"type", "name", "description", "body"}
	print(f"MemoryCandidate schema: {candidate.model_json_schema()['title']}")

	print("agents/schemas: self-test passed")
