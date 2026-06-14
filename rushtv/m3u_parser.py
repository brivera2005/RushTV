"""M3U playlist URL fetch and parse."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from rushtv.xtream import Channel, XtreamError

REQUEST_TIMEOUT = 30
M3U_MARKERS = ("#EXTM3U", "#EXTINF")


@dataclass
class M3UEntry:
    name: str
    url: str
    logo: str
    group: str
    tvg_id: str


def is_m3u_url(url: str) -> bool:
    lower = url.strip().lower()
    if lower.endswith((".m3u", ".m3u8")):
        return True
    if "get.php" in lower and "type=m3u" in lower:
        return True
    if "type=m3u_plus" in lower:
        return True
    return False


def fetch_m3u_text(url: str, username: str = "", password: str = "") -> str:
    headers = {"User-Agent": "RushTV/1.0"}
    try:
        response = requests.get(
            url.strip(),
            headers=headers,
            auth=(username, password) if username and password else None,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise XtreamError(f"Failed to download playlist: {exc}") from exc

    text = response.text
    if not any(marker in text for marker in M3U_MARKERS):
        raise XtreamError("URL does not appear to be a valid M3U playlist.")
    return text


def _parse_attr(line: str, key: str) -> str:
    pattern = rf'{key}="([^"]*)"'
    match = re.search(pattern, line, re.IGNORECASE)
    return match.group(1) if match else ""


def parse_m3u(text: str) -> list[M3UEntry]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    entries: list[M3UEntry] = []
    pending: dict[str, Any] | None = None

    for line in lines:
        if line.startswith("#EXTINF"):
            title = line.split(",")[-1].strip() if "," in line else "Unknown"
            pending = {
                "name": title,
                "logo": _parse_attr(line, "tvg-logo"),
                "group": _parse_attr(line, "group-title") or "Uncategorized",
                "tvg_id": _parse_attr(line, "tvg-id"),
            }
        elif not line.startswith("#") and pending is not None:
            entries.append(
                M3UEntry(
                    name=str(pending["name"]),
                    url=line,
                    logo=str(pending["logo"]),
                    group=str(pending["group"]),
                    tvg_id=str(pending["tvg_id"]),
                )
            )
            pending = None

    if not entries:
        raise XtreamError("No channels found in M3U playlist.")
    return entries


def entries_to_channels(entries: list[M3UEntry]) -> tuple[list[dict[str, str]], list[Channel]]:
    groups: dict[str, int] = {}
    categories: list[dict[str, str]] = []
    channels: list[Channel] = []

    for index, entry in enumerate(entries):
        group = entry.group or "Uncategorized"
        if group not in groups:
            cat_id = str(len(groups))
            groups[group] = len(categories)
            categories.append({"category_id": cat_id, "name": group})

        category_id = str(groups[group])
        channels.append(
            Channel(
                stream_id=index + 1,
                name=entry.name,
                category_id=category_id,
                logo=entry.logo,
                stream_type="m3u",
            )
        )

    return categories, channels


def channel_play_url(entry_index: int, entries: list[M3UEntry]) -> str:
    if entry_index < 1 or entry_index > len(entries):
        raise XtreamError("Invalid channel.")
    return entries[entry_index - 1].url


def xtream_credentials_from_m3u_url(url: str) -> tuple[str, str, str] | None:
    """Extract server, user, pass from Xtream-style get.php M3U links."""
    parsed = urlparse(url.strip())
    if "get.php" not in parsed.path.lower():
        return None
    query = parsed.query or ""
    params = dict(
        part.split("=", 1)
        for part in query.split("&")
        if "=" in part
    )
    username = params.get("username", "")
    password = params.get("password", "")
    if not username or not password:
        return None
    server = f"{parsed.scheme}://{parsed.netloc}"
    return server, username, password
