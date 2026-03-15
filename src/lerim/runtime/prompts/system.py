"""System prompt helpers for the PydanticAI Lerim lead runtime."""

from __future__ import annotations


def build_lead_system_prompt(max_explorers: int = 4) -> str:
    """Build compact system instructions for the lead orchestration agent."""
    if max_explorers > 1:
        explore_rule = f"- You can call up to {max_explorers} explore() calls in the SAME tool-call turn for parallel execution when you have independent queries."
    else:
        explore_rule = "- Call one explore() call per turn."
    return f"""\
You are LerimAgent, the lead runtime orchestrator.
Rules:
- Keep memory operations deterministic and explicit.
- Use tools for filesystem actions; do not fabricate file content.
- NEVER read or write paths outside memory_root, workspace, or run_folder. All file operations MUST use paths rooted in these directories. Do NOT attempt to read /, /tmp, home directories, or any path not under your assigned roots.
- For candidate evidence gathering, delegate the read-only explorer subagent via explore(query).
{explore_rule}
- Prefer concise, structured outputs."""


if __name__ == "__main__":
    prompt = build_lead_system_prompt()
    assert "LerimAgent" in prompt
    assert "read-only explorer subagent" in prompt
    print("system prompt: self-test passed")
