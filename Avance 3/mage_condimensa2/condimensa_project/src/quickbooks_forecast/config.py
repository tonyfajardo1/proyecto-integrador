from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load config and attach resolved project paths."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path

    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    config = deepcopy(config)
    paths = config["paths"]
    raw_dir = PROJECT_ROOT / paths["raw_dir"]

    resolved = {
        "project_root": PROJECT_ROOT,
        "raw_dir": raw_dir,
        "input_dir": PROJECT_ROOT / paths.get("input_dir", "data/input"),
        "catalog": raw_dir / paths["catalog_file"],
        "sales": raw_dir / paths["sales_file"],
        "production": raw_dir / paths["production_file"],
        "costs": raw_dir / paths.get("costs_file", "Costos.xlsx"),
        "interim_dir": PROJECT_ROOT / paths["interim_dir"],
        "processed_dir": PROJECT_ROOT / paths["processed_dir"],
        "models_dir": PROJECT_ROOT / paths["models_dir"],
        "reports_dir": PROJECT_ROOT / paths["reports_dir"],
    }
    config["resolved_paths"] = resolved
    return config


def ensure_output_dirs(config: dict[str, Any]) -> None:
    for key in ["interim_dir", "processed_dir", "models_dir", "reports_dir"]:
        config["resolved_paths"][key].mkdir(parents=True, exist_ok=True)
