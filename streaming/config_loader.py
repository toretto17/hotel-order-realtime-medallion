"""
Load pipeline configuration from config/pipeline.yaml with env var substitution.

Why config over code (interview-ready):
- Topic names, paths, watermark delay, checkpoint paths all live in one file.
- We can change behavior per environment (dev/staging/prod) by overriding env vars
  (e.g. KAFKA_BOOTSTRAP_SERVERS, BASE_PATH) without changing code.
- Same binary runs everywhere; 12-factor style.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

# Default: repo root = parent of 'streaming'
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _REPO_ROOT / "config" / "pipeline.yaml"

# Pattern: ${VAR} or ${VAR:-default}
_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def _substitute_env(value: Any) -> Any:
    """Replace ${VAR:-default} in strings; recurse into dicts and lists."""
    if isinstance(value, str):
        def replacer(match: re.Match) -> str:
            key = match.group(1).strip()
            default = match.group(2)
            return os.environ.get(key, default) if default is not None else os.environ.get(key, "")

        return _ENV_PATTERN.sub(replacer, value)
    if isinstance(value, dict):
        return {k: _substitute_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(v) for v in value]
    return value


def load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """
    Load pipeline.yaml and substitute environment variables.
    Returns a dict with keys: kafka, streaming, paths, postgres.
    """
    path = Path(config_path) if config_path else _CONFIG_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not raw:
        raise ValueError("Config file is empty")

    return _substitute_env(raw)


def get_kafka_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Kafka section: bootstrap_servers, topic_orders, topic_dlq, consumer_group, starting_offsets."""
    cfg = config or load_config()
    return cfg.get("kafka", {})


def get_streaming_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Streaming section: trigger_interval, watermark_delay, allowed_lateness, etc."""
    cfg = config or load_config()
    return cfg.get("streaming", {})


def get_paths_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Paths section: base, checkpoints, bronze/silver/gold paths."""
    cfg = config or load_config()
    return cfg.get("paths", {})


# Convenience: one-liner for jobs
def get_pipeline_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load full config; use in every streaming/batch job."""
    return load_config(config_path)
