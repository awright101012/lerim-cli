"""One-time script to compact existing eval traces in-place.

Applies per-agent compaction (drops noise lines) to Claude and Codex traces
in evals/dataset/traces/. Cursor and OpenCode traces are already compact.
"""

from pathlib import Path

from lerim.adapters.claude import compact_trace as compact_claude
from lerim.adapters.codex import compact_trace as compact_codex

TRACES_DIR = Path(__file__).resolve().parent.parent / "dataset" / "traces"


def main() -> None:
    """Compact all Claude and Codex eval traces in-place."""
    for trace_path in sorted(TRACES_DIR.glob("*.jsonl")):
        name = trace_path.name
        raw = trace_path.read_text(encoding="utf-8")
        original_size = len(raw)

        if name.startswith("claude_"):
            compacted = compact_claude(raw)
        elif name.startswith("codex_"):
            compacted = compact_codex(raw)
        else:
            continue

        trace_path.write_text(compacted, encoding="utf-8")
        new_size = len(compacted)
        ratio = (1 - new_size / original_size) * 100 if original_size else 0
        print(f"{name}: {original_size:,} -> {new_size:,} ({ratio:.1f}% reduction)")


if __name__ == "__main__":
    main()
