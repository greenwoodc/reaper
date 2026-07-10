"""Shared config loading, previously copy-pasted in every phase script."""

import re
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

CONFIG_FILE = "config.yml"

DEFAULTS = {
    "navidrome_url": "http://localhost:4533/",
    "navidrome_user": "admin",
    "navidrome_password": "",
    "navidrome_client": "reaper",
    "navidrome_version": "1.16.1",
    "match_threshold": 0.80,
    # "desc" = highest rank first → #1 last (countdown feel)
    # "asc"  = #1 first (good for shuffle play)
    "playlist_order": "desc",
}


def load_config() -> dict:
    """Load config from config.yml, falling back to defaults."""
    config = dict(DEFAULTS)
    config_path = Path(CONFIG_FILE)

    if not config_path.exists():
        print(f"[WARN] {CONFIG_FILE} not found — using defaults. Run: cp config.example.yaml config.yml")
        return config

    if yaml is None:
        print("[WARN] pyyaml not installed — pip install pyyaml. Using defaults.")
        return config

    with open(config_path) as f:
        loaded = yaml.safe_load(f) or {}

    config.update({k: v for k, v in loaded.items() if v is not None})
    return config


def slugify(name: str) -> str:
    """Convert a playlist name or filename to a filesystem-safe slug."""
    name = re.sub(r'[^\w\s-]', '', name.lower())
    name = re.sub(r'[\s_-]+', '_', name)
    return name.strip('_')
