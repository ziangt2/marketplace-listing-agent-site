"""Repository-relative, isolated paths and explicit experiment configuration."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "default.json"


def load_config(path=DEFAULT_CONFIG):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def manifest_path(profile):
    return ROOT / "data" / "manifests" / f"catalog_{profile}.jsonl"


def queries_path(profile):
    return ROOT / "data" / "manifests" / f"queries_{profile}_v2.jsonl"
