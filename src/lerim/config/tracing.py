"""MLflow tracing for DSPy agent observability.

Activates MLflow autologging for DSPy when ``LERIM_MLFLOW=true`` is set.
All DSPy module calls, LM interactions, and tool invocations are captured
automatically — no manual span instrumentation needed.

Traces are stored in a local SQLite database (~/.lerim/mlflow.db).
External OTel OTLP export is disabled to avoid noise when no collector runs.
"""

from __future__ import annotations

import os

import mlflow
import mlflow.dspy
from loguru import logger

from lerim.config.settings import Config


def configure_tracing(config: Config, experiment_name: str = "lerim") -> None:
	"""Activate MLflow DSPy autologging if enabled via LERIM_MLFLOW env var.

	Must be called once at startup before any agent is constructed.

	Args:
		config: Lerim config (must have mlflow_enabled=True to take effect).
		experiment_name: MLflow experiment to log into. Use "lerim" for production
			runs and "lerim-evals" (or any custom name) for evaluation runs so they
			show up in separate tabs in the MLflow UI.
	"""
	if not config.mlflow_enabled:
		return

	# Disable external OTel OTLP export — we use MLflow's SQLite backend only.
	# Without this, a stale OTEL_EXPORTER_OTLP_ENDPOINT env var causes
	# "Exception while exporting Span" errors on every LLM call.
	os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
	os.environ.pop("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", None)

	db_path = config.global_data_dir / "mlflow.db"
	mlflow.set_tracking_uri(f"sqlite:///{db_path}")
	mlflow.set_experiment(experiment_name)
	mlflow.dspy.autolog()
	logger.info(
		"MLflow tracing enabled (DSPy autolog) → sqlite:///{} experiment={}",
		db_path,
		experiment_name,
	)


if __name__ == "__main__":
	"""Minimal self-test: configure_tracing runs without error."""
	from lerim.config.settings import load_config

	cfg = load_config()
	configure_tracing(cfg)
	state = "enabled" if cfg.mlflow_enabled else "disabled"
	print(f"tracing.py self-test passed (mlflow {state})")
