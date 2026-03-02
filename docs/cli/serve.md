# lerim serve

Start the HTTP API server, dashboard, and daemon loop in a single process.

## Overview

`lerim serve` is the all-in-one runtime process. It starts three components together:

1. **HTTP API** — REST endpoints used by CLI commands (`ask`, `sync`, `maintain`, `status`)
2. **Dashboard** — Web UI served at the same host/port
3. **Daemon loop** — Background sync and maintain cycles on configured intervals

This is the Docker container entrypoint (`lerim up` runs `lerim serve` inside the container), but it can also be run directly for development without Docker.

!!! info
    For Docker-based usage, prefer `lerim up` which handles container lifecycle, volume mounts, and config generation automatically. Use `lerim serve` directly when developing or running without Docker.

## Syntax

```bash
lerim serve [--host HOST] [--port PORT]
```

## Parameters

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--host</span>
    <span class="param-type">string</span>
    <span class="param-badge default">default: 0.0.0.0</span>
  </div>
  <p class="param-desc">Network interface to bind to. Use <code>0.0.0.0</code> to listen on all interfaces (required for Docker), or <code>127.0.0.1</code> for local-only access.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--port</span>
    <span class="param-type">integer</span>
    <span class="param-badge default">default: 8765</span>
  </div>
  <p class="param-desc">TCP port to listen on. The API and dashboard are both served on this port.</p>
</div>

## Examples

### Start with defaults

```bash
lerim serve
```

**Output:**

```
Lerim v0.4.0 starting...
  API:       http://0.0.0.0:8765/api
  Dashboard: http://0.0.0.0:8765
  Daemon:    sync every 10m, maintain every 60m

Server ready.
```

### Custom bind address

```bash
# Local-only access on a custom port
lerim serve --host 127.0.0.1 --port 9000
```

### Development workflow

```bash
# Install in editable mode and run directly
uv pip install -e .
lerim serve
```

!!! tip
    When running `lerim serve` directly (not via Docker), make sure your config exists at `~/.lerim/config.toml`. Run `lerim init` first if needed.

## What it starts

| Component | Description | Endpoint |
|-----------|-------------|----------|
| HTTP API | REST API for CLI commands | `http://<host>:<port>/api/` |
| Dashboard | Web UI for browsing memories and runs | `http://<host>:<port>/` |
| Daemon loop | Background sync/maintain on intervals | — (internal) |

The daemon loop uses the same intervals as `lerim daemon`: `sync_interval_minutes` (default 10) and `maintain_interval_minutes` (default 60) from `~/.lerim/config.toml`.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Clean shutdown (SIGINT/SIGTERM) |
| `1` | Startup failure (port in use, config missing) |

## Related commands

<div class="grid cards" markdown>

-   :material-arrow-up-bold: **lerim up**

    ---

    Start Lerim via Docker (runs `serve` inside)

    [:octicons-arrow-right-24: lerim up](up-down-logs.md)

-   :material-refresh: **lerim daemon**

    ---

    Standalone daemon loop (no API/dashboard)

    [:octicons-arrow-right-24: lerim daemon](daemon.md)

-   :material-monitor-dashboard: **lerim dashboard**

    ---

    Print the dashboard URL

    [:octicons-arrow-right-24: lerim dashboard](dashboard.md)

-   :material-chart-box: **lerim status**

    ---

    Check server health and runtime state

    [:octicons-arrow-right-24: lerim status](status.md)

</div>
