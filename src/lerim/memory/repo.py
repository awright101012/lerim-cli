"""Filesystem paths and layout helpers for Lerim memory.

MemoryRepository has been removed. The agent reads/writes memory files directly
via SDK tools. This module keeps standalone path helpers used by settings and CLI.

Flat memory directory — all memories live
in memory/ directly. Summaries stay in memory/summaries/. Archived in memory/archived/.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


@dataclass(frozen=True)
class MemoryPaths:
    """Resolved canonical paths for one Lerim data root."""

    data_dir: Path
    memory_dir: Path
    workspace_dir: Path
    index_dir: Path


def build_memory_paths(data_dir: Path) -> MemoryPaths:
    """Build canonical path set rooted at ``data_dir``."""
    data_dir = data_dir.expanduser()
    return MemoryPaths(
        data_dir=data_dir,
        memory_dir=data_dir / "memory",
        workspace_dir=data_dir / "workspace",
        index_dir=data_dir / "index",
    )


def ensure_memory_paths(paths: MemoryPaths) -> None:
    """Create required canonical memory folders when missing."""
    for path in (
        paths.memory_dir,
        paths.memory_dir / "summaries",
        paths.memory_dir / "archived",
        paths.workspace_dir,
        paths.index_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)


def reset_memory_root(paths: MemoryPaths) -> dict[str, list[str]]:
    """Delete memory/index/workspace/cache trees for a root and recreate canonical layout.

    Also clears the adapter cache (compacted session traces) so the next sync
    re-discovers and re-filters sessions from scratch.
    """
    removed: list[str] = []
    cache_dir = paths.data_dir / "cache"
    for path in (paths.memory_dir, paths.workspace_dir, paths.index_dir, cache_dir):
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
            removed.append(str(path))
    ensure_memory_paths(paths)
    return {"removed": removed}


if __name__ == "__main__":
    """Run a real-path smoke test for memory path helpers."""
    with TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        paths = build_memory_paths(root)

        # Verify path structure
        assert paths.data_dir == root
        assert paths.memory_dir == root / "memory"
        assert paths.workspace_dir == root / "workspace"
        assert paths.index_dir == root / "index"

        # Ensure creates folders
        ensure_memory_paths(paths)
        assert paths.memory_dir.exists()
        assert (paths.memory_dir / "summaries").exists()
        assert (paths.memory_dir / "archived").exists()
        assert paths.workspace_dir.exists()
        assert paths.index_dir.exists()

        # Reset removes and recreates
        (paths.memory_dir / "test.md").write_text("test", encoding="utf-8")
        result = reset_memory_root(paths)
        assert str(paths.memory_dir) in result["removed"]
        assert paths.memory_dir.exists()
        assert not (paths.memory_dir / "test.md").exists()

    print("memory_repo: self-test passed")
