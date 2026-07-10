"""Shared Subsonic/Navidrome API client, previously duplicated across all four
phase scripts (auth token, api_get, connection check)."""

import hashlib
import json
import sys
from typing import Optional
from urllib import request, parse
from urllib.error import URLError

SALT = "reaper"


def subsonic_token(password: str, salt: str = SALT) -> str:
    return hashlib.md5((password + salt).encode()).hexdigest()


def _auth_params(config: dict) -> dict:
    return {
        "u": config["navidrome_user"],
        "t": subsonic_token(config["navidrome_password"]),
        "s": SALT,
        "v": config["navidrome_version"],
        "c": config["navidrome_client"],
        "f": "json",
    }


def make_api_get(config: dict):
    """Return a simple api_get(endpoint, params) -> dict function bound to config.

    Used for search3/ping/startScan/getScanStatus — anything that doesn't need
    repeated query-string keys.
    """
    base_url = config["navidrome_url"].rstrip("/")
    auth_base = _auth_params(config)

    def api_get(endpoint: str, params: dict) -> dict:
        merged = {**auth_base, **params}
        url = f"{base_url}/rest/{endpoint}?" + parse.urlencode(merged)
        try:
            with request.urlopen(url, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    return {}
                response = payload.get("subsonic-response", {})
                if response.get("status") not in (None, "ok"):
                    return {}
                return payload
        except URLError:
            return {}

    return api_get


def make_api(config: dict):
    """Return (api_get, api_raw, base_url, auth_str) bound to config.

    api_raw takes a fully-built URL directly — needed for updatePlaylist,
    which requires repeated query keys (songIdToAdd=...&songIdToAdd=...)
    that urlencode can't express from a dict.
    """
    base_url = config["navidrome_url"].rstrip("/")
    auth_str = parse.urlencode(_auth_params(config))

    def _parse(resp_bytes: bytes, endpoint: str) -> Optional[dict]:
        payload = json.loads(resp_bytes)
        response = payload.get("subsonic-response", {})
        if response.get("status") not in (None, "ok"):
            print(f"  [ERROR] API returned status={response.get('status')} for {endpoint}")
            return None
        return payload

    def api_get(endpoint: str, params: dict) -> Optional[dict]:
        query = parse.urlencode(params)
        url = f"{base_url}/rest/{endpoint}?{auth_str}&{query}"
        try:
            with request.urlopen(url, timeout=15) as resp:
                return _parse(resp.read(), endpoint)
        except URLError as e:
            print(f"  [ERROR] {e}")
            return None

    def api_raw(url: str) -> Optional[dict]:
        try:
            with request.urlopen(url, timeout=15) as resp:
                return _parse(resp.read(), url)
        except URLError as e:
            print(f"  [ERROR] {e}")
            return None

    return api_get, api_raw, base_url, auth_str


def check_connection(api_get, quiet: bool = False) -> bool:
    """Verify Navidrome is reachable and credentials are valid.

    CLI callers keep today's sys.exit(1)-on-failure behavior; Flask callers
    pass quiet=True and check the return value instead of dying.
    """
    resp = api_get("ping.view", {})
    status = resp.get("subsonic-response", {}).get("status")
    if status != "ok":
        if quiet:
            return False
        print("❌  Cannot reach Navidrome — check config.yml URL and credentials.")
        sys.exit(1)
    if not quiet:
        print("✓ Navidrome connection verified.")
    return True
