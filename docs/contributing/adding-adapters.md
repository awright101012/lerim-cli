# Adding Adapters

Adding a platform adapter is the most common Lerim contribution. This guide
walks through the process step by step.

## Overview

An adapter teaches Lerim how to read session transcripts from a coding agent
platform. Each adapter implements the `Adapter` protocol defined in
`src/lerim/adapters/base.py`.

## Step 1: Create the adapter file

Create `src/lerim/adapters/<platform>.py` with a top-level docstring.

Your adapter must implement these 5 functions:

### `default_path() -> Path | None`

Return the default directory where this platform stores session traces.
Return `None` if there is no standard location.

```python
from pathlib import Path

def default_path() -> Path | None:
    """Return the default traces directory for <platform>."""
    p = Path.home() / ".myagent" / "sessions"
    return p if p.exists() else None
```

### `count_sessions(path: Path) -> int`

Return the total number of sessions found under `path`.

```python
def count_sessions(path: Path) -> int:
    """Return total session count under ``path``."""
    return len(list(path.glob("*.jsonl")))
```

### `iter_sessions(traces_dir, start, end, known_run_hashes) -> list[SessionRecord]`

List normalized session summaries within a time window. Return a list of
`SessionRecord` objects (imported from `lerim.adapters.base`).

```python
from datetime import datetime
from lerim.adapters.base import SessionRecord

def iter_sessions(
    traces_dir: Path | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    known_run_hashes: dict[str, str] | None = None,
) -> list[SessionRecord]:
    """List normalized session summaries in the selected time window."""
    records = []
    # ... parse session files, filter by time window ...
    return records
```

### `find_session_path(session_id, traces_dir) -> Path | None`

Resolve a single session file path by session ID.

```python
def find_session_path(
    session_id: str, traces_dir: Path | None = None
) -> Path | None:
    """Resolve one session file path by ``session_id``."""
    # ... locate the file ...
    return path if path.exists() else None
```

### `read_session(session_path, session_id) -> ViewerSession | None`

Read one session file and return a normalized `ViewerSession` payload.

```python
from lerim.adapters.base import ViewerMessage, ViewerSession

def read_session(
    session_path: Path, session_id: str | None = None
) -> ViewerSession | None:
    """Read one session file and return a normalized viewer payload."""
    messages = []
    # ... parse the session file into ViewerMessage objects ...
    return ViewerSession(
        session_id=session_id or session_path.stem,
        messages=messages,
    )
```

!!! tip "Reference implementations"
    Look at existing adapters for patterns:

    - `src/lerim/adapters/codex.py` -- straightforward JSONL parsing
    - `src/lerim/adapters/claude.py` -- JSONL with project directory structure
    - `src/lerim/adapters/cursor.py` -- SQLite to JSONL export
    - `src/lerim/adapters/opencode.py` -- SQLite to JSONL export

## Step 2: Register in registry.py

Open `src/lerim/adapters/registry.py` and add your platform:

```python
_ADAPTER_MODULES: dict[str, str] = {
    "claude": "lerim.adapters.claude",
    "codex": "lerim.adapters.codex",
    "opencode": "lerim.adapters.opencode",
    "cursor": "lerim.adapters.cursor",
    "myagent": "lerim.adapters.myagent",  # <-- add this
}
```

If the platform should be auto-detected by `lerim connect auto`, also add it
to `_AUTO_SEED_PLATFORMS`:

```python
_AUTO_SEED_PLATFORMS = ("claude", "codex", "opencode", "cursor", "myagent")
```

## Step 3: Add unit tests

Create `tests/unit/test_<platform>_adapter.py`:

```python
"""Unit tests for the <platform> adapter."""

from pathlib import Path
from lerim.adapters import myagent


def test_default_path():
    """default_path returns a Path or None."""
    result = myagent.default_path()
    assert result is None or isinstance(result, Path)


def test_count_sessions_empty(tmp_path):
    """count_sessions returns 0 for an empty directory."""
    assert myagent.count_sessions(tmp_path) == 0


def test_iter_sessions_empty(tmp_path):
    """iter_sessions returns empty list for empty directory."""
    result = myagent.iter_sessions(traces_dir=tmp_path)
    assert result == []
```

Add fixture trace files to `tests/fixtures/traces/` if your adapter needs
sample data for parsing tests.

!!! warning "Test quality"
    Tests should validate actual parsing behavior, not just check that functions
    exist. Include fixture files with realistic session data.

## Step 4: Update tests/README.md

Add your new test file to the unit test table in `tests/README.md`:

```markdown
| `test_myagent_adapter.py` | MyAgent adapter parsing and session discovery |
```

## Checklist

- [ ] Adapter file created at `src/lerim/adapters/<platform>.py` with docstring
- [ ] All 5 protocol functions implemented
- [ ] Registered in `_ADAPTER_MODULES` in `registry.py`
- [ ] Added to `_AUTO_SEED_PLATFORMS` if auto-detection makes sense
- [ ] Unit tests in `tests/unit/test_<platform>_adapter.py`
- [ ] Fixture traces in `tests/fixtures/traces/` (if needed)
- [ ] `tests/README.md` updated
- [ ] `ruff check src/ tests/` passes
- [ ] `tests/run_tests.sh unit` passes
