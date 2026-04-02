"""Tests for canonical memory layout creation and root reset behavior."""

from __future__ import annotations

from lerim.memory.repo import (
    build_memory_paths,
    ensure_memory_paths,
    reset_memory_root,
)


def test_ensure_memory_paths_creates_canonical_folders(tmp_path) -> None:
    layout = build_memory_paths(tmp_path)
    ensure_memory_paths(layout)

    assert layout.memory_dir.exists()
    assert (layout.memory_dir / "summaries").exists()
    assert (layout.memory_dir / "archived").exists()
    assert layout.workspace_dir.exists()
    assert layout.index_dir.exists()


def test_reset_memory_root_recreates_clean_layout(tmp_path) -> None:
    layout = build_memory_paths(tmp_path)
    ensure_memory_paths(layout)

    memory_file = layout.memory_dir / "example--l20260220abcd.md"
    memory_file.write_text("seed", encoding="utf-8")
    stale_index = layout.index_dir / "fts.sqlite3"
    stale_index.write_text("", encoding="utf-8")

    result = reset_memory_root(layout)

    removed = set(result["removed"])
    assert str(layout.memory_dir) in removed
    assert str(layout.index_dir) in removed
    assert layout.memory_dir.exists()
    assert not memory_file.exists()
    assert not stale_index.exists()
