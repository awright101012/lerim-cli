"""Unit tests for memory candidate Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lerim.agents.schemas import MemoryCandidate


# --- Valid types ---


@pytest.mark.parametrize("mem_type", ["user", "feedback", "project", "reference"])
def test_memory_candidate_valid_types(mem_type: str):
    """All four valid types are accepted."""
    c = MemoryCandidate(
        type=mem_type,
        name=f"Name for {mem_type}",
        description=f"Description for {mem_type}",
        body=f"Body content for {mem_type}",
    )
    assert c.type == mem_type
    assert c.name == f"Name for {mem_type}"
    assert c.description == f"Description for {mem_type}"
    assert c.body == f"Body content for {mem_type}"


# --- Invalid type ---


@pytest.mark.parametrize(
    "bad_type",
    ["decision", "learning", "summary", "pitfall", "insight", "procedure", "bogus"],
)
def test_memory_candidate_invalid_type(bad_type: str):
    """Old primitive values and arbitrary strings are rejected."""
    with pytest.raises(ValidationError):
        MemoryCandidate(
            type=bad_type,
            name="Bad",
            description="Should fail",
            body="Body",
        )


# --- Required fields ---


def test_memory_candidate_missing_name():
    """Missing name -> ValidationError."""
    with pytest.raises(ValidationError):
        MemoryCandidate(type="user", description="desc", body="body")


def test_memory_candidate_missing_description():
    """Missing description -> ValidationError."""
    with pytest.raises(ValidationError):
        MemoryCandidate(type="user", name="name", body="body")


def test_memory_candidate_missing_body():
    """Missing body -> ValidationError."""
    with pytest.raises(ValidationError):
        MemoryCandidate(type="user", name="name", description="desc")


def test_memory_candidate_missing_type():
    """Missing type -> ValidationError."""
    with pytest.raises(ValidationError):
        MemoryCandidate(name="name", description="desc", body="body")


# --- Schema stability ---


def test_memory_candidate_fields_exactly_four():
    """MemoryCandidate has exactly 4 fields: type, name, description, body."""
    assert set(MemoryCandidate.model_fields.keys()) == {
        "type",
        "name",
        "description",
        "body",
    }


def test_memory_candidate_json_schema():
    """model_json_schema() produces valid JSON Schema dict with expected properties."""
    schema = MemoryCandidate.model_json_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema
    assert set(schema["properties"].keys()) == {"type", "name", "description", "body"}


def test_memory_candidate_model_validate():
    """model_validate from dict works correctly."""
    c = MemoryCandidate.model_validate(
        {
            "type": "feedback",
            "name": "Never truncate logs",
            "description": "Always show full content in UI and logs.",
            "body": "Detailed explanation of the feedback preference.",
        }
    )
    assert c.type == "feedback"
    assert c.name == "Never truncate logs"


def test_memory_candidate_empty_strings_accepted():
    """Empty strings for name/description/body are accepted by Pydantic (plain str)."""
    c = MemoryCandidate(type="user", name="", description="", body="")
    assert c.name == ""
    assert c.description == ""
    assert c.body == ""
