# Querying Memories

Lerim provides several ways to search and retrieve memories. All queries are
read-only and project-scoped.

## `lerim ask` -- LLM-powered Q&A

The primary query interface. Sends your question to the lead agent with memory
context.

!!! note "Requires running server"
    `lerim ask` is a service command that requires `lerim up` or `lerim serve`
    to be running.

### Basic query

```bash
lerim ask "Why did we choose Postgres over SQLite?"
```

The lead agent retrieves relevant memories, uses them as context, and returns
a natural language answer with evidence of which memories were consulted.

### Limit context

Control how many memory items are included as context:

```bash
lerim ask "What auth pattern do we use?" --limit 5
```

| Flag | Default | Description |
|------|---------|-------------|
| `question` | required | Your question (quote if it contains spaces) |
| `--project` | -- | Scope to a specific project (not yet implemented) |
| `--limit` | `12` | Max memory items provided as context |

### JSON output

Get structured output for scripting or agent integration:

```bash
lerim ask "How is the database configured?" --json
```

Returns JSON with the answer, sources, and metadata.

## `lerim memory search` -- keyword search

Full-text keyword search across memory titles, bodies, and tags. Runs locally
on the host -- no server required.

```bash
lerim memory search "database migration"
```

```bash
lerim memory search pytest --limit 5
```

| Flag | Default | Description |
|------|---------|-------------|
| `query` | required | Search string to match (case-insensitive) |
| `--project` | -- | Filter to project (not yet implemented) |
| `--limit` | `20` | Max results |

!!! tip "When to use search vs ask"
    Use `memory search` for quick keyword lookups when you know what you're
    looking for. Use `ask` when you need the LLM to reason about your question
    and synthesize an answer from multiple memories.

## `lerim memory list` -- browse all memories

List stored memories (decisions and learnings), ordered by recency:

```bash
lerim memory list
```

```bash
lerim memory list --limit 10
```

```bash
lerim memory list --json
```

| Flag | Default | Description |
|------|---------|-------------|
| `--project` | -- | Filter to project (not yet implemented) |
| `--limit` | `50` | Max items |

## Tips for effective queries

### Be specific

```bash
# Good -- specific topic
lerim ask "What authentication pattern does the API use?"

# Less effective -- too broad
lerim ask "How does auth work?"
```

### Reference past decisions

```bash
lerim ask "Why did we switch from REST to gRPC for the internal API?"
lerim ask "What problems did we have with the original caching approach?"
```

### Check before implementing

At the start of a coding session, ask your agent:

> Check lerim for any relevant memories about [topic you're working on].

Your agent will run `lerim ask` or `lerim memory search` to pull in past
decisions and learnings before it starts working.

### Combine search and ask

```bash
# Quick lookup to see what exists
lerim memory search "database"

# Then ask a specific question
lerim ask "What was the rationale for the database migration strategy?"
```
