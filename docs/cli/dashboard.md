# lerim dashboard

Print the dashboard URL.

## Overview

A convenience command that prints the URL of the Lerim web dashboard. The dashboard itself is served by `lerim serve` (or `lerim up` via Docker) — this command simply outputs the URL so you can open it in a browser.

## Syntax

```bash
lerim dashboard
```

## Parameters

This command takes no parameters.

## Examples

```bash
lerim dashboard
```

**Output:**

```
Dashboard: http://localhost:8765
```

!!! tip
    The dashboard is available as long as `lerim serve` or `lerim up` is running. If the server is not running, the URL will not be reachable.

## Dashboard tabs

The web dashboard provides five tabs:

=== "Overview"

    Summary view showing connected platforms, total memory count, session queue depth, and recent activity. A quick health-check at a glance.

=== "Runs"

    History of sync and maintain runs. Each entry shows timestamp, duration, sessions processed, memories created/updated/archived, and LLM cost.

=== "Memories"

    Browse all stored memories (decisions and learnings) across registered projects. Filter by primitive type, kind, tags, or confidence. View full memory content and metadata.

=== "Pipeline"

    Inspect the extraction and maintenance pipeline. See DSPy module inputs/outputs, deduplication decisions, and merge operations for each run.

=== "Settings"

    View and edit `config.toml` values: connected platforms, sync/maintain intervals, search mode toggles, and project list.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success — URL printed |

## Related commands

<div class="grid cards" markdown>

-   :material-server: **lerim serve**

    ---

    Start the server that hosts the dashboard

    [:octicons-arrow-right-24: lerim serve](serve.md)

-   :material-arrow-up-bold: **lerim up**

    ---

    Start Lerim via Docker

    [:octicons-arrow-right-24: lerim up](up-down-logs.md)

-   :material-chart-box: **lerim status**

    ---

    Check server state from the CLI

    [:octicons-arrow-right-24: lerim status](status.md)

</div>
