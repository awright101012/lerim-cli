"""Thin wrapper that invokes coding agent CLIs as judge.

Supports claude, codex, and opencode as judge agents. Reads prompt templates
from judge_prompts/ and injects trace path + pipeline output. Uses structured
output flags (--json-schema for claude, --output-schema for codex) and retries
on JSON parse failure.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from lerim.config.logging import logger


# JSON schema for judge responses with clarity dimension (extraction, summarization)
JUDGE_SCHEMA_CLARITY = {
    "type": "object",
    "properties": {
        "completeness": {"type": "number"},
        "faithfulness": {"type": "number"},
        "clarity": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["completeness", "faithfulness", "clarity", "reasoning"],
    "additionalProperties": False,
}

# JSON schema for judge responses with coherence dimension (lifecycle sync/maintain)
JUDGE_SCHEMA_COHERENCE = {
    "type": "object",
    "properties": {
        "completeness": {"type": "number"},
        "faithfulness": {"type": "number"},
        "coherence": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["completeness", "faithfulness", "coherence", "reasoning"],
    "additionalProperties": False,
}

MAX_RETRIES = 2


def _run_with_heartbeat(
    cmd: list[str], timeout: int, interval: int = 30
) -> subprocess.CompletedProcess:
    """Run a subprocess with periodic heartbeat logs.

    Uses Popen + a daemon thread that logs every ``interval`` seconds
    so long-running judge calls don't appear stuck.
    """
    stop = threading.Event()
    start = time.time()

    def _heartbeat():
        while not stop.wait(interval):
            logger.info(
                "  Judge still running... ({:.0f}s elapsed)", time.time() - start
            )

    t = threading.Thread(target=_heartbeat, daemon=True)
    t.start()
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            raise subprocess.TimeoutExpired(cmd, timeout, output=stdout, stderr=stderr)
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    finally:
        stop.set()
        t.join(timeout=2)


def _build_cmd(
    agent: str, prompt: str, model: str | None, schema: dict | None
) -> tuple[list[str], Path | None]:
    """Build CLI command and optional temp schema file.

    Returns (cmd, temp_schema_path). Caller must delete temp_schema_path
    if not None.
    """
    temp_schema_path = None

    if agent == "claude":
        cmd = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--allowedTools",
            "Read",
        ]
        if model:
            cmd.extend(["--model", model])
        if schema:
            cmd.extend(["--json-schema", json.dumps(schema)])
    elif agent == "codex":
        cmd = ["codex", "exec", prompt, "--json", "--ephemeral"]
        if model:
            cmd.extend(["--model", model])
        if schema:
            f = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                prefix="judge_schema_",
                delete=False,
            )
            json.dump(schema, f)
            f.close()
            temp_schema_path = Path(f.name)
            cmd.extend(["--output-schema", str(temp_schema_path)])
    elif agent == "opencode":
        cmd = ["opencode", "run", prompt, "--format", "json"]
        if model:
            cmd.extend(["--model", model])
        # opencode has no structured output flag
    else:
        raise ValueError(f"Unknown judge agent: {agent}")

    return cmd, temp_schema_path


def invoke_judge(
    agent: str,
    prompt: str,
    timeout: int = 120,
    model: str | None = None,
    schema: dict | None = None,
) -> dict:
    """Invoke a coding agent CLI as judge, return parsed JSON.

    Retries up to MAX_RETRIES times on JSON parse failures. Uses structured
    output flags when available (--json-schema for claude, --output-schema
    for codex).
    """
    if schema is None:
        schema = JUDGE_SCHEMA_CLARITY

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        cmd, temp_schema_path = _build_cmd(agent, prompt, model, schema)
        try:
            result = _run_with_heartbeat(cmd, timeout)
            if result.returncode != 0:
                raise RuntimeError(
                    f"Judge {agent} failed (rc={result.returncode}): {result.stderr[:500]}"
                )
            return _parse_agent_output(agent, result.stdout)
        except RuntimeError as e:
            last_error = e
            if "Could not parse JSON" in str(e) and attempt < MAX_RETRIES:
                logger.warning(
                    "Judge parse error (attempt {}/{}), retrying: {}",
                    attempt,
                    MAX_RETRIES,
                    e,
                )
                continue
            raise
        finally:
            if temp_schema_path and temp_schema_path.exists():
                temp_schema_path.unlink()

    raise last_error  # type: ignore[misc]


def _parse_agent_output(agent: str, raw: str) -> dict:
    """Parse structured JSON output from coding agent CLI."""
    # For claude --output-format json, structured data is in 'structured_output'
    # field (when --json-schema is used), while 'result' contains prose text.
    if agent == "claude":
        try:
            wrapper = json.loads(raw)
            if isinstance(wrapper, dict):
                # Prefer structured_output (set by --json-schema)
                structured = wrapper.get("structured_output")
                if isinstance(structured, dict):
                    return structured
                text = wrapper.get("result", raw)
            else:
                text = raw
        except (json.JSONDecodeError, TypeError):
            text = raw
    else:
        text = raw

    # Try direct JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    # Fall back to extracting JSON from markdown code blocks
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            pass

    raise RuntimeError(f"Could not parse JSON from {agent} output: {text[:300]}")


def build_judge_prompt(
    template_path: Path, trace_path: Path, pipeline_output: str
) -> str:
    """Read judge prompt template and inject trace path + pipeline output."""
    template = template_path.read_text(encoding="utf-8")
    return template.replace("{trace_path}", str(trace_path)).replace(
        "{output}", pipeline_output
    )


if __name__ == "__main__":
    """Self-test for judge utilities."""
    # Test _parse_agent_output with direct JSON
    assert _parse_agent_output("codex", '{"completeness": 0.8}') == {
        "completeness": 0.8
    }

    # Test _parse_agent_output with claude structured_output field (--json-schema)
    wrapper = json.dumps(
        {
            "result": "Done! Returned the evaluation.",
            "structured_output": {
                "completeness": 0.9,
                "faithfulness": 0.8,
                "clarity": 0.7,
                "reasoning": "test",
            },
        }
    )
    assert _parse_agent_output("claude", wrapper) == {
        "completeness": 0.9,
        "faithfulness": 0.8,
        "clarity": 0.7,
        "reasoning": "test",
    }

    # Test _parse_agent_output with claude result fallback (no structured_output)
    wrapper = json.dumps({"result": '{"completeness": 0.9}'})
    assert _parse_agent_output("claude", wrapper) == {"completeness": 0.9}

    # Test _parse_agent_output with markdown code block
    md = 'Some text\n```json\n{"clarity": 0.7}\n```\nmore text'
    assert _parse_agent_output("codex", md) == {"clarity": 0.7}

    # Test build_judge_prompt
    import tempfile as _tmp

    with _tmp.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("Evaluate {trace_path}\nOutput: {output}")
        f.flush()
        prompt = build_judge_prompt(
            Path(f.name), Path("/tmp/trace.jsonl"), '{"data": 1}'
        )
        assert "/tmp/trace.jsonl" in prompt
        assert '{"data": 1}' in prompt

    # Test _build_cmd with schema for claude
    cmd, tmp = _build_cmd("claude", "test prompt", None, JUDGE_SCHEMA_CLARITY)
    assert "--json-schema" in cmd
    assert tmp is None

    # Test _build_cmd with schema for codex
    cmd, tmp = _build_cmd("codex", "test prompt", None, JUDGE_SCHEMA_CLARITY)
    assert "--output-schema" in cmd
    assert tmp is not None
    tmp.unlink()

    # Test schema constants have right keys
    assert set(JUDGE_SCHEMA_CLARITY["required"]) == {
        "completeness",
        "faithfulness",
        "clarity",
        "reasoning",
    }
    assert set(JUDGE_SCHEMA_COHERENCE["required"]) == {
        "completeness",
        "faithfulness",
        "coherence",
        "reasoning",
    }

    print("judge: self-test passed")
