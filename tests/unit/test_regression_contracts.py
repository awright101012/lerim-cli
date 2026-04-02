"""Regression and contract stability tests for Lerim runtime schemas."""

from __future__ import annotations


def test_sync_result_contract_fields():
    """SyncResultContract has exactly these fields."""
    from lerim.agents.contracts import SyncResultContract

    expected = {
        "trace_path",
        "memory_root",
        "workspace_root",
        "run_folder",
        "artifacts",
        "counts",
        "written_memory_paths",
        "summary_path",
        "cost_usd",
    }
    assert set(SyncResultContract.model_fields.keys()) == expected


def test_maintain_result_contract_fields():
    """MaintainResultContract has exactly these fields."""
    from lerim.agents.contracts import MaintainResultContract

    expected = {
        "memory_root",
        "workspace_root",
        "run_folder",
        "artifacts",
        "counts",
        "cost_usd",
    }
    assert set(MaintainResultContract.model_fields.keys()) == expected


def test_sync_counts_fields():
    """SyncCounts has add, update, no_op."""
    from lerim.agents.contracts import SyncCounts

    assert set(SyncCounts.model_fields.keys()) == {"add", "update", "no_op"}


def test_maintain_counts_fields():
    """MaintainCounts has merged, archived, consolidated, unchanged."""
    from lerim.agents.contracts import MaintainCounts

    assert set(MaintainCounts.model_fields.keys()) == {
        "merged",
        "archived",
        "consolidated",
        "unchanged",
    }


def test_memory_candidate_schema_stable():
    """MemoryCandidate has type, name, description, body."""
    from lerim.agents.schemas import MemoryCandidate

    expected = {"type", "name", "description", "body"}
    assert set(MemoryCandidate.model_fields.keys()) == expected


def test_cli_subcommands_present():
    """CLI parser has all expected subcommands."""
    from lerim.server.cli import build_parser

    parser = build_parser()
    # Extract subcommand names from the parser
    subparsers_actions = [
        a for a in parser._subparsers._actions if hasattr(a, "_parser_class")
    ]
    choices: set[str] = set()
    for action in subparsers_actions:
        if hasattr(action, "choices") and action.choices:
            choices.update(action.choices.keys())
    for cmd in (
        "connect",
        "sync",
        "maintain",
        "serve",
        "ask",
        "memory",
        "dashboard",
        "status",
        "queue",
        "retry",
        "skip",
    ):
        assert cmd in choices, f"Missing CLI subcommand: {cmd}"


def test_memory_record_frontmatter_keys():
    """MemoryRecord.to_frontmatter_dict() produces expected keys."""
    from lerim.agents.schemas import MemoryRecord

    record = MemoryRecord(
        id="contract-test",
        type="user",
        name="Contract Test",
        description="Testing frontmatter contract.",
        body="Body",
        source="test",
    )
    fm = record.to_frontmatter_dict()
    expected = {"name", "description", "type", "id", "created", "updated", "source"}
    assert set(fm.keys()) == expected
