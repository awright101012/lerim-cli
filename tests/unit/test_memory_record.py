"""Unit tests for memory taxonomy, record model, and markdown helpers."""

from __future__ import annotations

import frontmatter

from lerim.agents.schemas import (
    MemoryRecord,
    MemoryType,
    canonical_memory_filename,
    slugify,
)


# --- slugify tests (unchanged) ---


def test_slugify_normal():
    """Normal title -> lowercase hyphenated slug."""
    assert slugify("Hello World") == "hello-world"


def test_slugify_special_chars():
    """Special characters stripped, spaces become hyphens."""
    assert slugify("Use JWT (HS256)!") == "use-jwt-hs256"


def test_slugify_unicode():
    """Unicode chars transliterated or stripped."""
    result = slugify("cafe resume")
    assert result  # non-empty
    assert "caf" in result


def test_slugify_empty():
    """Empty string -> 'memory' fallback."""
    assert slugify("") == "memory"
    assert slugify("   ") == "memory"


def test_slugify_long():
    """Very long title still produces a valid slug."""
    long_title = "A" * 500
    result = slugify(long_title)
    assert len(result) > 0
    assert result.isascii()


# --- canonical_memory_filename tests (unchanged) ---


def test_canonical_memory_filename():
    """canonical_memory_filename produces YYYYMMDD-slug.md format."""
    fname = canonical_memory_filename(
        title="My Title", run_id="sync-20260220-120000-abc123"
    )
    assert fname == "20260220-my-title.md"


def test_canonical_memory_filename_with_run_id_date():
    """When run_id contains a date, it's used for the prefix."""
    fname = canonical_memory_filename(
        title="Test", run_id="sync-20260115-093000-def456"
    )
    assert fname.startswith("20260115-")
    assert fname.endswith(".md")


# --- MemoryType enum tests ---


def test_memory_type_enum_values():
    """MemoryType has user, feedback, project, reference, summary."""
    expected = {"user", "feedback", "project", "reference", "summary"}
    actual = {m.value for m in MemoryType}
    assert actual == expected


def test_memory_type_enum_members():
    """All expected members are accessible as attributes."""
    assert MemoryType.user.value == "user"
    assert MemoryType.feedback.value == "feedback"
    assert MemoryType.project.value == "project"
    assert MemoryType.reference.value == "reference"
    assert MemoryType.summary.value == "summary"


# --- MemoryRecord tests (new 3-field frontmatter: name, description, type) ---


def test_memory_record_to_markdown_roundtrip():
    """MemoryRecord -> to_markdown() -> parse with python-frontmatter -> same fields."""
    record = MemoryRecord(
        id="test-record",
        type="user",
        name="Test Record",
        description="A short description of the record.",
        body="This is the body content.",
        source="test-run",
    )
    md = record.to_markdown()
    parsed = frontmatter.loads(md)
    assert parsed["id"] == "test-record"
    assert parsed["name"] == "Test Record"
    assert parsed["description"] == "A short description of the record."
    assert parsed["type"] == "user"
    assert parsed.content.strip() == "This is the body content."


def test_memory_record_to_frontmatter_dict():
    """to_frontmatter_dict() has expected keys."""
    record = MemoryRecord(
        id="rec-1",
        type="project",
        name="Project Decision",
        description="Describes a project decision.",
        body="Body text",
        source="run-1",
    )
    fm = record.to_frontmatter_dict()
    expected_keys = {"name", "description", "type", "id", "created", "updated", "source"}
    assert set(fm.keys()) == expected_keys


def test_memory_record_all_types():
    """MemoryRecord accepts all valid type values."""
    for t in ("user", "feedback", "project", "reference"):
        record = MemoryRecord(
            id=f"rec-{t}",
            type=t,
            name=f"Name for {t}",
            description=f"Desc for {t}",
            body="Body",
            source="test",
        )
        assert record.type == t


def test_memory_record_frontmatter_no_extra_keys():
    """to_frontmatter_dict() has no unexpected keys."""
    record = MemoryRecord(
        id="rec-2",
        type="feedback",
        name="Feedback item",
        description="Feedback description.",
        body="Body",
        source="run-2",
    )
    fm = record.to_frontmatter_dict()
    allowed = {"name", "description", "type", "id", "created", "updated", "source"}
    assert set(fm.keys()) <= allowed
