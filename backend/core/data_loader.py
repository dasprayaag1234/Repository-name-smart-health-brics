"""
Loads datasets described in datasets/dataset_config.json.

For each dataset: if the CSV exists at the configured path AND has all required
columns, it's loaded and flagged as real. Otherwise the dataset is reported
missing/invalid so the caller (management command / API) can fall back to
demo data and label it accordingly in the UI. Nothing here silently invents
numbers — it only ever reports what it found.
"""
import json
import logging
from pathlib import Path

import pandas as pd
from django.conf import settings

logger = logging.getLogger(__name__)


class DatasetLoadResult:
    def __init__(self, name, ok, df=None, reason=""):
        self.name = name
        self.ok = ok
        self.df = df
        self.reason = reason

    def __repr__(self):
        return f"<DatasetLoadResult {self.name} ok={self.ok} reason={self.reason!r}>"


def get_config():
    config_path = settings.DATASETS_DIR / "dataset_config.json"
    with open(config_path) as f:
        return json.load(f)


def _load_csv(path: Path, required_columns):
    if not path.exists():
        return DatasetLoadResult(path.name, False, reason=f"file not found: {path}")
    try:
        df = pd.read_csv(path)
    except Exception as e:  # noqa: BLE001 - want to report any parse error, not just crash
        return DatasetLoadResult(path.name, False, reason=f"could not parse CSV: {e}")
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        return DatasetLoadResult(path.name, False, reason=f"missing required columns: {missing}")
    if df.empty:
        return DatasetLoadResult(path.name, False, reason="file is present but empty")
    return DatasetLoadResult(path.name, True, df=df)


def load_all():
    """
    Returns a dict {dataset_name: DatasetLoadResult}. Datasets that fail
    validation still get an entry (ok=False, reason=...) so callers can
    show exactly what's missing rather than failing silently.
    """
    config = get_config()
    results = {}
    for name, spec in config["datasets"].items():
        if name == "brics":
            # multi-file pattern
            countries = spec["countries"]
            per_country = {}
            for country in countries:
                rel = spec["path_pattern"].format(country=country)
                per_country[country] = _load_csv(settings.DATASETS_DIR / rel, spec["required_columns"])
            all_ok = all(r.ok for r in per_country.values())
            results[name] = {
                "ok": all_ok,
                "per_country": per_country,
            }
            continue
        results[name] = _load_csv(settings.DATASETS_DIR / spec["path"], spec["required_columns"])
    return results


def summarize(results):
    """Human-readable summary of what real data was found vs what's missing."""
    lines = []
    for name, res in results.items():
        if name == "brics":
            found = [c for c, r in res["per_country"].items() if r.ok]
            missing = [c for c, r in res["per_country"].items() if not r.ok]
            lines.append(f"brics: {len(found)}/{len(res['per_country'])} countries present ({', '.join(found) or 'none'})")
            continue
        status = "FOUND" if res.ok else f"MISSING ({res.reason})"
        lines.append(f"{name}: {status}")
    return "\n".join(lines)
