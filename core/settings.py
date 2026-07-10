"""Read/write the settings surfaced by the webapp's Settings page:
config.yml (Navidrome + matching), config/sldl.conf (Soulseek + download
prefs), and .env (host media/incoming directories used by docker-compose.yml
and download_missing.sh/move_to_library.sh).

This module is the write path the webapp uses to edit those same files.
"""

import yaml
from pathlib import Path

from core.config import CONFIG_FILE, DEFAULTS, load_config

SLDL_CONF_PATH = Path("config/sldl.conf")
ENV_PATH = Path(".env")
DEFAULT_MEDIA_ROOT = "/mnt/media"

# sldl.conf keys the Settings page manages, and their "primary" vs "advanced"
# grouping. Any other keys already in the file (listen-port, name-format,
# min-shares-aggregate, etc.) are preserved untouched on write.
_ADVANCED_KEY_MAP = {
    "concurrent_jobs": "concurrent-jobs",
    "concurrent_searches": "concurrent-searches",
    "searches_per_time": "searches-per-time",
    "searches_renew_time": "searches-renew-time",
    "search_timeout": "search-timeout",
    "max_stale_time": "max-stale-time",
}


def _parse_properties(text: str) -> list[tuple[str | None, str | None, str]]:
    """Parse a sldl.conf-style 'key = value' file into (key, value, raw_line)
    triples, preserving comments/blank lines (key=None) and original order."""
    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw:
            lines.append((None, None, raw))
            continue
        key, value = raw.split("=", 1)
        lines.append((key.strip(), value.strip(), raw))
    return lines


def read_sldl_conf(path: Path = SLDL_CONF_PATH) -> dict:
    if not path.exists():
        return {}
    text = path.read_text()
    return {k: v for k, v, _raw in _parse_properties(text) if k is not None}


def write_sldl_conf(updates: dict[str, str], path: Path = SLDL_CONF_PATH) -> None:
    """Update only the given keys, preserving every other line untouched.
    Keys not already present in the file are appended."""
    text = path.read_text() if path.exists() else ""
    lines = _parse_properties(text)

    remaining = dict(updates)
    out = []
    for key, _value, raw in lines:
        if key is not None and key in remaining:
            out.append(f"{key} = {remaining.pop(key)}")
        else:
            out.append(raw)
    for key, value in remaining.items():
        out.append(f"{key} = {value}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n")


def _read_env_var(key: str, default: str = "") -> str:
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if line.strip().startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return default


def _write_env_var(key: str, value: str) -> None:
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


def read_media_root() -> str:
    return _read_env_var("REAPER_MEDIA_ROOT", DEFAULT_MEDIA_ROOT)


def write_media_root(value: str) -> None:
    _write_env_var("REAPER_MEDIA_ROOT", value)


def read_incoming_dir() -> str:
    """The staging dir for fresh downloads awaiting beets import. Empty
    return means "not overridden" — callers should derive the effective
    value as f"{media_root}/incoming"."""
    return _read_env_var("REAPER_INCOMING_DIR", "")


def write_incoming_dir(value: str) -> None:
    _write_env_var("REAPER_INCOMING_DIR", value)


def read_puid() -> str:
    """The host UID that must own the media/incoming folders — the sockseek
    container runs as this uid (docker-compose.yml's PUID), and beets needs
    matching ownership on what it downloads to move/tag files."""
    return _read_env_var("PUID", "1000")


def write_puid(value: str) -> None:
    _write_env_var("PUID", value)


def read_pgid() -> str:
    return _read_env_var("PGID", "1000")


def write_pgid(value: str) -> None:
    _write_env_var("PGID", value)


def get_settings() -> dict:
    """Return the current settings, with unset/empty passwords reported only
    as a `_set` boolean — actual secret values are never sent back to the
    frontend once saved."""
    config = load_config()
    sldl = read_sldl_conf()
    media_root = read_media_root()

    return {
        "navidrome": {
            "url": config["navidrome_url"],
            "user": config["navidrome_user"],
            "password_set": bool(config.get("navidrome_password")),
        },
        "matching": {
            "match_threshold": config["match_threshold"],
            "playlist_order": config.get("playlist_order", "desc"),
        },
        "soulseek": {
            "username": sldl.get("username", ""),
            "password_set": bool(sldl.get("password")),
        },
        "download": {
            "format": sldl.get("format", "mp3,flac,ogg"),
            "pref_format": sldl.get("pref-format", "flac"),
            "pref_min_bitrate": sldl.get("pref-min-bitrate", "256"),
            "desperate": sldl.get("desperate", "true") == "true",
            "skip_existing": sldl.get("skip-existing", "true") == "true",
        },
        "advanced": {
            camel: sldl.get(conf_key, DEFAULTS.get(camel, ""))
            for camel, conf_key in _ADVANCED_KEY_MAP.items()
        }
        | {"fast_search": sldl.get("fast-search", "false") == "true"},
        "paths": {
            "media_root": media_root,
            "incoming_dir": read_incoming_dir() or f"{media_root}/incoming",
            "puid": read_puid(),
            "pgid": read_pgid(),
        },
    }


def update_settings(payload: dict) -> None:
    config_path = Path(CONFIG_FILE)
    existing = {}
    if config_path.exists():
        existing = yaml.safe_load(config_path.read_text()) or {}

    nav = payload.get("navidrome") or {}
    if nav.get("url"):
        existing["navidrome_url"] = nav["url"]
    if nav.get("user"):
        existing["navidrome_user"] = nav["user"]
    if nav.get("password"):
        existing["navidrome_password"] = nav["password"]

    matching = payload.get("matching") or {}
    if "match_threshold" in matching:
        existing["match_threshold"] = float(matching["match_threshold"])
    if matching.get("playlist_order"):
        existing["playlist_order"] = matching["playlist_order"]

    config_path.write_text(yaml.safe_dump(existing, sort_keys=False, default_flow_style=False))

    sldl_updates: dict[str, str] = {}

    soulseek = payload.get("soulseek") or {}
    if soulseek.get("username"):
        sldl_updates["username"] = soulseek["username"]
    if soulseek.get("password"):
        sldl_updates["password"] = soulseek["password"]

    download = payload.get("download") or {}
    if download.get("format"):
        sldl_updates["format"] = download["format"]
    if download.get("pref_format"):
        sldl_updates["pref-format"] = download["pref_format"]
    if "pref_min_bitrate" in download:
        sldl_updates["pref-min-bitrate"] = str(download["pref_min_bitrate"])
    if "desperate" in download:
        sldl_updates["desperate"] = "true" if download["desperate"] else "false"
    if "skip_existing" in download:
        sldl_updates["skip-existing"] = "true" if download["skip_existing"] else "false"

    advanced = payload.get("advanced") or {}
    for camel, conf_key in _ADVANCED_KEY_MAP.items():
        if camel in advanced and advanced[camel] != "":
            sldl_updates[conf_key] = str(advanced[camel])
    if "fast_search" in advanced:
        sldl_updates["fast-search"] = "true" if advanced["fast_search"] else "false"

    if sldl_updates:
        write_sldl_conf(sldl_updates)

    paths = payload.get("paths") or {}
    if paths.get("media_root"):
        write_media_root(paths["media_root"])

    if "incoming_dir" in paths:
        effective_media_root = paths.get("media_root") or read_media_root()
        default_incoming = f"{effective_media_root}/incoming"
        incoming_value = paths["incoming_dir"] or default_incoming
        # Only persist an override when it actually differs from the derived
        # default — keeps .env clean and avoids a stale override surviving a
        # later media_root change that the user didn't also update here.
        write_incoming_dir("" if incoming_value == default_incoming else incoming_value)

    if paths.get("puid"):
        write_puid(str(paths["puid"]))
    if paths.get("pgid"):
        write_pgid(str(paths["pgid"]))
