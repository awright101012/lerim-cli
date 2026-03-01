# lerim memory

Manage the memory store directly — search, list, add, and reset memories.

## Overview

The `memory` command group provides direct access to the memory store. Memories are stored as markdown files in `.lerim/memory/` within each registered project. Use these subcommands to search, browse, manually create, or wipe memories.

!!! note
    Subcommands that read memory (`search`, `list`) require a running server. Start it with `lerim up` (Docker) or `lerim serve` (direct).

---

## memory search

Full-text keyword search across memory titles, bodies, and tags (case-insensitive).

### Syntax

```bash
lerim memory search <query> [--limit N]
```

### Parameters

<div class="param-field">
  <div class="param-header">
    <span class="param-name">query</span>
    <span class="param-type">string</span>
    <span class="param-badge required">required</span>
  </div>
  <p class="param-desc">Search string to match against memory titles, bodies, and tags.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--limit</span>
    <span class="param-type">integer</span>
    <span class="param-badge default">default: 20</span>
  </div>
  <p class="param-desc">Maximum number of results to return.</p>
</div>

### Examples

```bash
# Search for database-related memories
lerim memory search 'database migration'
```

```bash
# Narrow results
lerim memory search pytest --limit 5
```

**Output:**

```
Found 3 memories matching "pytest":

  [learning] use-pytest-fixtures (0.85)
    Use pytest fixtures for database setup instead of manual teardown

  [decision] test-runner-choice (0.92)
    Chose pytest over unittest for its fixture system and plugin ecosystem

  [learning] pytest-parallel-safe (0.70)
    Mark tests that touch shared state with @pytest.mark.serial
```

---

## memory list

List stored memories (decisions and learnings), ordered by recency.

### Syntax

```bash
lerim memory list [--limit N] [--json]
```

### Parameters

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--limit</span>
    <span class="param-type">integer</span>
    <span class="param-badge default">default: 50</span>
  </div>
  <p class="param-desc">Maximum number of items to display.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--json</span>
    <span class="param-type">boolean</span>
    <span class="param-badge default">default: false</span>
  </div>
  <p class="param-desc">Output structured JSON instead of human-readable text.</p>
</div>

### Examples

```bash
# List recent memories
lerim memory list
```

```bash
# Show only the 10 most recent
lerim memory list --limit 10
```

**Output:**

```
Memories (12 total, showing 10):

  2026-02-28  [decision]  api-auth-pattern       (0.92)  Use bearer tokens for all API endpoints
  2026-02-27  [learning]  uv-faster-than-pip     (0.85)  uv resolves deps 10x faster than pip
  2026-02-26  [learning]  pytest-fixture-scope   (0.80)  Prefer session-scoped fixtures for DB
  2026-02-25  [decision]  monorepo-structure     (0.88)  Keep services in packages/ subdirectory
  ...
```

=== "Human-readable"

    ```bash
    lerim memory list --limit 5
    ```

=== "JSON"

    ```bash
    lerim memory list --limit 5 --json
    ```

    ```json
    {
      "total": 12,
      "items": [
        {
          "id": "api-auth-pattern",
          "primitive": "decision",
          "title": "API auth pattern",
          "confidence": 0.92,
          "created": "2026-02-28T14:30:00Z",
          "tags": ["auth", "api"]
        }
      ]
    }
    ```

---

## memory add

Manually create a single memory record. Useful for codifying decisions or learnings that didn't come from an agent session.

### Syntax

```bash
lerim memory add --title <TITLE> --body <BODY> [options]
```

### Parameters

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--title</span>
    <span class="param-type">string</span>
    <span class="param-badge required">required</span>
  </div>
  <p class="param-desc">Short descriptive title for the memory.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--body</span>
    <span class="param-type">string</span>
    <span class="param-badge required">required</span>
  </div>
  <p class="param-desc">Full body content of the memory.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--primitive</span>
    <span class="param-type">string</span>
    <span class="param-badge default">default: learning</span>
  </div>
  <p class="param-desc">Memory primitive type: <code>decision</code> or <code>learning</code>.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--kind</span>
    <span class="param-type">string</span>
    <span class="param-badge default">default: insight</span>
  </div>
  <p class="param-desc">Memory kind: <code>insight</code>, <code>procedure</code>, <code>friction</code>, <code>pitfall</code>, or <code>preference</code>.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--confidence</span>
    <span class="param-type">float</span>
    <span class="param-badge default">default: 0.7</span>
  </div>
  <p class="param-desc">Confidence score from 0.0 to 1.0.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--tags</span>
    <span class="param-type">string</span>
  </div>
  <p class="param-desc">Comma-separated tags (e.g. <code>python,testing,ci</code>).</p>
</div>

### Examples

```bash
# Add a simple learning
lerim memory add --title "Use uv for deps" --body "uv is faster than pip for dependency resolution"
```

```bash
# Add a decision with explicit primitive
lerim memory add --title "API auth" --body "Use bearer tokens for all endpoints" --primitive decision
```

```bash
# Full options
lerim memory add \
    --title "Slow integration tests" \
    --body "Integration suite takes 5 min — run in parallel where possible" \
    --kind friction \
    --confidence 0.9 \
    --tags ci,testing
```

**Output:**

```
Created memory: slow-integration-tests
  primitive: learning
  kind:      friction
  confidence: 0.90
  tags:      ci, testing
  path:      .lerim/memory/learnings/slow-integration-tests.md
```

!!! tip
    Manually added memories go through the same deduplication check as extracted ones. If a similar memory already exists, Lerim will warn you.

---

## memory reset

Irreversibly delete `memory/`, `workspace/`, and `index/` under the selected scope.

### Syntax

```bash
lerim memory reset --yes [--scope SCOPE]
```

### Parameters

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--scope</span>
    <span class="param-type">string</span>
    <span class="param-badge default">default: both</span>
  </div>
  <p class="param-desc">What to reset: <code>project</code> (current project's <code>.lerim/</code>), <code>global</code> (<code>~/.lerim/index/</code> and caches), or <code>both</code>.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--yes</span>
    <span class="param-type">boolean</span>
    <span class="param-badge required">required</span>
  </div>
  <p class="param-desc">Safety flag — the command refuses to run without it.</p>
</div>

!!! warning
    `--scope project` alone does **not** reset the session queue. The sessions database lives in the global `index/` (`~/.lerim/index/sessions.sqlite3`). Use `--scope global` or `--scope both` to fully reset the session queue.

!!! danger
    This operation is **irreversible**. All memories, workspace artifacts, and index data within the selected scope will be permanently deleted.

### Examples

```bash
# Wipe everything (both scopes)
lerim memory reset --yes
```

```bash
# Reset only the current project's data
lerim memory reset --scope project --yes
```

```bash
# Fresh start: reset and re-sync a few sessions
lerim memory reset --yes && lerim sync --max-sessions 5
```

**Output:**

```
Resetting scope: both

Deleted:
  project memory:    .lerim/memory/       (24 files)
  project workspace: .lerim/workspace/    (8 directories)
  project index:     .lerim/index/        (1 file)
  global index:      ~/.lerim/index/      (1 file)
  global cache:      ~/.lerim/cache/      (3 files)

Reset complete.
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Runtime failure (server not running, write error) |
| `2` | Usage error (missing required flags) |

---

## Related commands

<div class="grid cards" markdown>

-   :material-magnify: **lerim ask**

    ---

    Query memories with natural language

    [:octicons-arrow-right-24: lerim ask](ask.md)

-   :material-sync: **lerim sync**

    ---

    Extract memories from agent sessions

    [:octicons-arrow-right-24: lerim sync](sync.md)

-   :material-wrench: **lerim maintain**

    ---

    Offline memory refinement and deduplication

    [:octicons-arrow-right-24: lerim maintain](maintain.md)

-   :material-chart-box: **lerim status**

    ---

    Check memory counts and server state

    [:octicons-arrow-right-24: lerim status](status.md)

</div>
