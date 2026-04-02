"""Typed runtime contracts and leaf utilities for orchestration.

This module is a leaf in the import graph -- it must NOT import from
runtime.py, tools.py, or any agent module to avoid circular imports.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Path guard (used by tools.py and runtime.py)
# ---------------------------------------------------------------------------

def is_within(path: Path, root: Path) -> bool:
	"""Return whether path equals or is inside root."""
	resolved = path.resolve()
	root_resolved = root.resolve()
	return resolved == root_resolved or root_resolved in resolved.parents


class SyncCounts(BaseModel):
	"""Stable sync count payload contract."""

	add: int = 0
	update: int = 0
	no_op: int = 0


class MaintainCounts(BaseModel):
	"""Stable maintain count payload contract."""

	merged: int = 0
	archived: int = 0
	consolidated: int = 0
	unchanged: int = 0


class SyncResultContract(BaseModel):
	"""Stable sync return payload schema used by CLI and daemon."""

	trace_path: str
	memory_root: str
	workspace_root: str
	run_folder: str
	artifacts: dict[str, str]
	counts: SyncCounts
	written_memory_paths: list[str]
	summary_path: str
	cost_usd: float = 0.0


class MaintainResultContract(BaseModel):
	"""Stable maintain return payload schema used by CLI and daemon."""

	memory_root: str
	workspace_root: str
	run_folder: str
	artifacts: dict[str, str]
	counts: MaintainCounts
	cost_usd: float = 0.0


if __name__ == "__main__":
	"""Run contract model smoke checks."""
	sync = SyncCounts(add=1, update=2, no_op=3)
	assert sync.model_dump() == {"add": 1, "update": 2, "no_op": 3}

	maintain = MaintainCounts(merged=1, archived=2, consolidated=3)
	assert maintain.unchanged == 0

	print("runtime contracts: self-test passed")
