"""VLC media player wrapper for Windows."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

VLC_SEARCH_PATHS = [
    Path(r"C:\Program Files\VideoLAN\VLC"),
    Path(r"C:\Program Files (x86)\VideoLAN\VLC"),
]


def find_vlc_path() -> Path | None:
    for base in VLC_SEARCH_PATHS:
        lib = base / "libvlc.dll"
        if lib.exists():
            return base
    return None


def configure_vlc() -> Path | None:
    vlc_dir = find_vlc_path()
    if vlc_dir is None:
        return None
    os.environ["VLC_PLUGIN_PATH"] = str(vlc_dir / "plugins")
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(vlc_dir))
    if sys.platform == "win32":
        os.environ["PATH"] = str(vlc_dir) + os.pathsep + os.environ.get("PATH", "")
    return vlc_dir


_vlc_dir = configure_vlc()

try:
    import vlc
except Exception:  # noqa: BLE001
    vlc = None  # type: ignore[assignment]


class VLCNotFoundError(Exception):
    pass


class VLCPlayer:
    def __init__(
        self,
        on_playing: Callable[[], None] | None = None,
        on_stopped: Callable[[], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        if vlc is None or _vlc_dir is None:
            raise VLCNotFoundError(
                "VLC is not installed or could not be loaded. "
                "Install VLC from https://www.videolan.org/vlc/"
            )
        self._on_playing = on_playing
        self._on_stopped = on_stopped
        self._on_error = on_error
        self.instance = vlc.Instance("--no-video-title-show", "--quiet")
        self.player = self.instance.media_player_new()
        self._events = self.player.event_manager()
        self._events.event_attach(vlc.EventType.MediaPlayerPlaying, self._handle_playing)
        self._events.event_attach(vlc.EventType.MediaPlayerStopped, self._handle_stopped)
        self._events.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._handle_error)
        self.current_url: str | None = None

    def _handle_playing(self, _event: object) -> None:
        if self._on_playing:
            self._on_playing()

    def _handle_stopped(self, _event: object) -> None:
        if self._on_stopped:
            self._on_stopped()

    def _handle_error(self, _event: object) -> None:
        if self._on_error:
            self._on_error("Playback error")

    def set_window(self, hwnd: int) -> None:
        if sys.platform == "win32":
            self.player.set_hwnd(hwnd)
        elif sys.platform.startswith("linux"):
            self.player.set_xwindow(hwnd)
        elif sys.platform == "darwin":
            self.player.set_nsobject(hwnd)

    def play(self, url: str) -> None:
        self.stop()
        self.current_url = url
        media = self.instance.media_new(url)
        self.player.set_media(media)
        self.player.play()

    def stop(self) -> None:
        if self.player.is_playing():
            self.player.stop()
        self.current_url = None

    def pause(self) -> None:
        self.player.pause()

    def is_playing(self) -> bool:
        return bool(self.player.is_playing())

    def release(self) -> None:
        try:
            self.stop()
            self.player.release()
        except Exception:  # noqa: BLE001
            pass


def vlc_available() -> bool:
    return vlc is not None and _vlc_dir is not None
