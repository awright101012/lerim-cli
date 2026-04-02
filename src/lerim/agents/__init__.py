"""Agent modules: extract, maintain, ask + shared tools and contracts."""

from __future__ import annotations

from typing import Any

__all__ = ["ExtractAgent", "MaintainAgent", "AskAgent"]


def __getattr__(name: str) -> Any:
	"""Lazy-load agent exports to avoid circular import cycles."""
	if name == "ExtractAgent":
		from lerim.agents.extract import ExtractAgent
		return ExtractAgent
	if name == "MaintainAgent":
		from lerim.agents.maintain import MaintainAgent
		return MaintainAgent
	if name == "AskAgent":
		from lerim.agents.ask import AskAgent
		return AskAgent
	raise AttributeError(name)
