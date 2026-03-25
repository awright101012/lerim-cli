"""Runtime exports for Lerim orchestration and provider builders.

Uses lazy __getattr__ to avoid circular imports:
runtime.__init__ -> runtime.agent -> runtime.tools -> memory.extract_pipeline -> ... -> runtime.__init__
"""

from __future__ import annotations

from typing import Any

__all__ = ["LerimAgent", "build_orchestration_model", "build_dspy_lm", "build_oai_context", "build_oai_model", "build_oai_model_from_role", "build_oai_fallback_models", "build_codex_options", "build_responses_proxy"]


def __getattr__(name: str) -> Any:
    """Lazy-load runtime exports to avoid circular import cycles."""
    if name == "LerimAgent":
        from lerim.runtime.agent import LerimAgent

        return LerimAgent
    if name == "build_orchestration_model":
        from lerim.runtime.providers import build_orchestration_model

        return build_orchestration_model
    if name == "build_dspy_lm":
        from lerim.runtime.providers import build_dspy_lm

        return build_dspy_lm
    raise AttributeError(name)
