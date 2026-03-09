"""Compare eval results across multiple runs and configs.

Reads all JSON result files from evals/results/, groups by pipeline,
and prints a rich comparison table showing scores, timings, and config info.

Usage: python evals/compare.py [--pipeline extraction|summarization|lifecycle]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.common import console, print_compare_table


RESULTS_DIR = Path(__file__).parent / "results"


def compare_results(pipeline_filter: str | None = None) -> None:
    """Load all result JSONs and print comparison tables."""
    if not RESULTS_DIR.exists():
        console.print("[yellow]No results directory found. Run evals first.[/]")
        return

    result_files = sorted(RESULTS_DIR.glob("*.json"))
    if not result_files:
        console.print("[yellow]No result files found in evals/results/.[/]")
        return

    # Group by pipeline
    groups: dict[str, list[dict]] = {}
    for path in result_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        pipeline = data.get("pipeline", "unknown")
        if pipeline_filter and pipeline != pipeline_filter:
            continue
        groups.setdefault(pipeline, []).append(data)

    if not groups:
        console.print(
            f"[yellow]No results found"
            f"{f' for pipeline={pipeline_filter}' if pipeline_filter else ''}.[/]"
        )
        return

    for pipeline, runs in sorted(groups.items()):
        print_compare_table(pipeline, runs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare eval results")
    parser.add_argument(
        "--pipeline",
        choices=["extraction", "summarization", "lifecycle"],
        help="Filter by pipeline",
    )
    args = parser.parse_args()
    compare_results(args.pipeline)
