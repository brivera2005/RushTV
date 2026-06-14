"""Xtream Codes API client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

REQUEST_TIMEOUT = 20


@dataclass
class Channel:
    stream_id: int
    name: str
    category_id: str
    logo: str
    stream_type: str = "live"

    @property
    def display_name(self) -> str:
        return self.name or f"Channel {self.stream_id}"


@dataclass
class Category:
    category_id: str
    name: str


class XtreamError(Exception):
    pass


class XtreamClient:
    def __init__(self, server_url: str, username: str, password: str) -> None:
        self.server_url = self._normalize_server(server_url)
        self.username = username.strip()
        self.password = password
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "RushTV/1.0"})
        self.user_info: dict[str, Any] = {}

    @staticmethod
    def _normalize_server(url: str) -> str:
        url = url.strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        parsed = urlparse(url)
        if not parsed.netloc:
            raise XtreamError("Invalid server URL.")
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def api_url(self) -> str:
        return f"{self.server_url}/player_api.php"

    def _get(self, **params: Any) -> Any:
        query = {"username": self.username, "password": self.password, **params}
        try:
            response = self._session.get(self.api_url, params=query, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise XtreamError(f"Connection failed: {exc}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise XtreamError("Server returned an invalid response.") from exc

    def authenticate(self) -> dict[str, Any]:
        data = self._get()
        if not isinstance(data, dict) or "user_info" not in data:
            raise XtreamError("Invalid credentials or unsupported server.")
        user_info = data.get("user_info") or {}
        if str(user_info.get("auth")) == "0":
            raise XtreamError("Invalid username or password.")
        status = str(user_info.get("status", "")).lower()
        if status and status not in ("active", "1", "true"):
            raise XtreamError(f"Account status: {user_info.get('status', 'inactive')}")
        self.user_info = user_info
        return data

    def get_live_categories(self) -> list[Category]:
        data = self._get(action="get_live_categories")
        if not isinstance(data, list):
            return []
        categories: list[Category] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            categories.append(
                Category(
                    category_id=str(item.get("category_id", "")),
                    name=str(item.get("category_name", "Unknown")),
                )
            )
        return categories

    def get_live_streams(self, category_id: str | None = None) -> list[Channel]:
        params: dict[str, Any] = {"action": "get_live_streams"}
        if category_id is not None:
            params["category_id"] = category_id
        data = self._get(**params)
        if not isinstance(data, list):
            return []
        channels: list[Channel] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                stream_id = int(item.get("stream_id", 0))
            except (TypeError, ValueError):
                continue
            channels.append(
                Channel(
                    stream_id=stream_id,
                    name=str(item.get("name", "")),
                    category_id=str(item.get("category_id", "")),
                    logo=str(item.get("stream_icon", "") or ""),
                )
            )
        return channels

    def stream_url(self, stream_id: int) -> str:
        return (
            f"{self.server_url}/live/{self.username}/{self.password}/{stream_id}.m3u8"
        )

    @staticmethod
    def looks_like_xtream(server_url: str) -> bool:
        url = server_url.strip().lower()
        if "player_api.php" in url:
            return True
        if "get.php" in url and "type=m3u" in url:
            return False
        return bool(url)
