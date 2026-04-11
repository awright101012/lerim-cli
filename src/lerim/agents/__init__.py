"""Agent modules: extract (PydanticAI three-pass), maintain, ask + shared tools.

`ExtractAgent` is no longer exported. Sync flow now uses the PydanticAI
three-pass pipeline in `lerim.agents.extract.run_extraction_three_pass`,
imported directly by the runtime. Maintain and ask remain DSPy ReAct modules.
"""

from __future__ import annotations

from typing import Any

__all__ = ["MaintainAgent", "AskAgent"]


def __getattr__(name: str) -> Any:
	"""Lazy-load agent exports to avoid circular import cycles."""
	if name == "MaintainAgent":
		from lerim.agents.maintain import MaintainAgent
		return MaintainAgent
	if name == "AskAgent":
		from lerim.agents.ask import AskAgent
		return AskAgent
	raise AttributeError(name)
