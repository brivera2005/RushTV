"""CustomTkinter UI for RushTV."""

from __future__ import annotations

import io
import threading
import tkinter as tk
from pathlib import Path
from typing import Any

import customtkinter as ctk
import requests
from PIL import Image

from rushtv.m3u_parser import (
    M3UEntry,
    channel_play_url,
    entries_to_channels,
    fetch_m3u_text,
    is_m3u_url,
    parse_m3u,
    xtream_credentials_from_m3u_url,
)
from rushtv.player import VLCNotFoundError, VLCPlayer, vlc_available
from rushtv.storage import clear_credentials, load_config, save_config
from rushtv.xtream import Category, Channel, XtreamClient, XtreamError

# RushTV brand
BRAND_RED = "#E31E24"
BRAND_BG = "#0D0D0D"
BRAND_SURFACE = "#1A1A1A"
BRAND_SURFACE_LIGHT = "#252525"
BRAND_TEXT = "#FFFFFF"
BRAND_MUTED = "#9A9A9A"

APP_TITLE = "RushTV - Local IPTV Streaming"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def asset_path(name: str) -> Path:
    if getattr(__import__("sys"), "frozen", False):
        base = Path(__import__("sys")._MEIPASS)  # type: ignore[attr-defined]
        return base / "assets" / name
    return ASSETS_DIR / name


class ImageCache:
    def __init__(self) -> None:
        self._cache: dict[str, ctk.CTkImage | None] = {}
        self._placeholder = self._make_placeholder()

    def _make_placeholder(self) -> ctk.CTkImage:
        img = Image.new("RGB", (48, 48), BRAND_SURFACE_LIGHT)
        draw = ImageDraw.Draw(img)
        draw.rectangle((4, 4, 43, 43), outline=BRAND_RED, width=2)
        draw.text((16, 14), "TV", fill=BRAND_RED)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(36, 36))

    def get(self, url: str) -> ctk.CTkImage:
        if not url:
            return self._placeholder
        if url in self._cache:
            return self._cache[url] or self._placeholder
        try:
            response = requests.get(url, timeout=8, headers={"User-Agent": "RushTV/1.0"})
            response.raise_for_status()
            pil = Image.open(io.BytesIO(response.content)).convert("RGBA")
            pil = pil.resize((48, 48), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(36, 36))
            self._cache[url] = ctk_img
            return ctk_img
        except Exception:  # noqa: BLE001
            self._cache[url] = None
            return self._placeholder


class RushTVApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(APP_TITLE)
        self.geometry("1280x720")
        self.minsize(960, 600)
        self.configure(fg_color=BRAND_BG)

        self._image_cache = ImageCache()
        self._client: XtreamClient | None = None
        self._mode = "xtream"
        self._m3u_entries: list[M3UEntry] = []
        self._categories: list[Category | dict[str, str]] = []
        self._all_channels: list[Channel] = []
        self._filtered_channels: list[Channel] = []
        self._selected_category_id: str | None = None
        self._current_channel: Channel | None = None
        self._channel_rows: list[dict[str, Any]] = []
        self._player: VLCPlayer | None = None
        self._loading = False
        self._channel_list_focus = 0

        icon_path = asset_path("icon.ico")
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:  # noqa: BLE001
                pass

        self._build_login()
        self._load_saved_credentials()

        self.bind("<Up>", self._on_key_up)
        self.bind("<Down>", self._on_key_down)
        self.bind("<Return>", self._on_key_enter)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI shell

    def _clear_body(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    def _set_status(self, connection: str = "", now_playing: str = "") -> None:
        if hasattr(self, "_status_conn"):
            self._status_conn.configure(text=connection)
        if hasattr(self, "_status_now"):
            self._status_now.configure(text=now_playing)

    # ------------------------------------------------------------------ Login

    def _build_login(self) -> None:
        self._clear_body()
        if self._player:
            self._player.stop()

        frame = ctk.CTkFrame(self, fg_color=BRAND_BG)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        logo = self._load_logo(size=(320, 180))
        if logo:
            ctk.CTkLabel(frame, image=logo, text="").pack(pady=(0, 8))
        else:
            ctk.CTkLabel(
                frame,
                text="RUSHTV",
                font=ctk.CTkFont(size=42, weight="bold"),
                text_color=BRAND_RED,
            ).pack(pady=(0, 4))
            ctk.CTkLabel(
                frame,
                text="LOCAL IPTV STREAMING",
                font=ctk.CTkFont(size=12),
                text_color=BRAND_MUTED,
            ).pack(pady=(0, 16))

        ctk.CTkLabel(
            frame,
            text="Server URL",
            anchor="w",
            text_color=BRAND_MUTED,
        ).pack(fill="x", padx=40)
        self._server_entry = ctk.CTkEntry(
            frame,
            width=380,
            placeholder_text="http://host:port or M3U playlist URL",
            fg_color=BRAND_SURFACE,
            border_color=BRAND_SURFACE_LIGHT,
        )
        self._server_entry.pack(pady=(4, 12), padx=40)

        ctk.CTkLabel(frame, text="Username", anchor="w", text_color=BRAND_MUTED).pack(
            fill="x", padx=40
        )
        self._user_entry = ctk.CTkEntry(
            frame, width=380, fg_color=BRAND_SURFACE, border_color=BRAND_SURFACE_LIGHT
        )
        self._user_entry.pack(pady=(4, 12), padx=40)

        ctk.CTkLabel(frame, text="Password", anchor="w", text_color=BRAND_MUTED).pack(
            fill="x", padx=40
        )
        self._pass_entry = ctk.CTkEntry(
            frame,
            width=380,
            show="*",
            fg_color=BRAND_SURFACE,
            border_color=BRAND_SURFACE_LIGHT,
        )
        self._pass_entry.pack(pady=(4, 12), padx=40)

        self._remember_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            frame,
            text="Remember me",
            variable=self._remember_var,
            fg_color=BRAND_RED,
            hover_color="#B8181D",
            text_color=BRAND_TEXT,
        ).pack(anchor="w", padx=40, pady=(0, 12))

        self._login_error = ctk.CTkLabel(frame, text="", text_color=BRAND_RED)
        self._login_error.pack(pady=(0, 8))

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(pady=(0, 8))

        self._login_btn = ctk.CTkButton(
            btn_row,
            text="Connect",
            width=180,
            height=40,
            corner_radius=20,
            fg_color=BRAND_RED,
            hover_color="#B8181D",
            command=self._on_connect,
        )
        self._login_btn.pack(side="left", padx=8)

        self._login_spinner = ctk.CTkProgressBar(
            frame, width=380, mode="indeterminate", progress_color=BRAND_RED
        )

        if not vlc_available():
            ctk.CTkLabel(
                frame,
                text="VLC not found - install from videolan.org/vlc",
                text_color="#FFB347",
                wraplength=380,
            ).pack(pady=(12, 0))

        self._set_status("Not connected", "")

    def _load_logo(self, size: tuple[int, int]) -> ctk.CTkImage | None:
        path = asset_path("logo.png")
        if not path.exists():
            return None
        try:
            pil = Image.open(path).convert("RGBA")
            pil = pil.resize(size, Image.Resampling.LANCZOS)
            return ctk.CTkImage(light_image=pil, dark_image=pil, size=size)
        except Exception:  # noqa: BLE001
            return None

    def _load_saved_credentials(self) -> None:
        cfg = load_config()
        if cfg.get("remember"):
            self._server_entry.insert(0, cfg.get("server_url", ""))
            self._user_entry.insert(0, cfg.get("username", ""))
            self._pass_entry.insert(0, cfg.get("password", ""))
            self._remember_var.set(True)

    def _on_connect(self) -> None:
        if self._loading:
            return
        server = self._server_entry.get().strip()
        username = self._user_entry.get().strip()
        password = self._pass_entry.get()

        if not server:
            self._login_error.configure(text="Enter a server URL or M3U link.")
            return

        self._login_error.configure(text="")
        self._set_login_loading(True)

        thread = threading.Thread(
            target=self._connect_worker,
            args=(server, username, password),
            daemon=True,
        )
        thread.start()

    def _set_login_loading(self, loading: bool) -> None:
        self._loading = loading
        if loading:
            self._login_btn.configure(state="disabled")
            self._login_spinner.pack(pady=8)
            self._login_spinner.start()
        else:
            self._login_btn.configure(state="normal")
            self._login_spinner.stop()
            self._login_spinner.pack_forget()

    def _connect_worker(self, server: str, username: str, password: str) -> None:
        try:
            if is_m3u_url(server):
                creds = xtream_credentials_from_m3u_url(server)
                if creds and not username:
                    server, username, password = creds
                text = fetch_m3u_text(server, username, password)
                entries = parse_m3u(text)
                categories_raw, channels = entries_to_channels(entries)
                categories = [
                    Category(category_id=c["category_id"], name=c["name"])
                    for c in categories_raw
                ]
                self.after(
                    0,
                    lambda: self._on_connect_success(
                        mode="m3u",
                        server=server,
                        username=username,
                        password=password,
                        categories=categories,
                        channels=channels,
                        m3u_entries=entries,
                        client=None,
                    ),
                )
            else:
                client = XtreamClient(server, username, password)
                client.authenticate()
                categories = client.get_live_categories()
                channels = client.get_live_streams()
                self.after(
                    0,
                    lambda: self._on_connect_success(
                        mode="xtream",
                        server=server,
                        username=username,
                        password=password,
                        categories=categories,
                        channels=channels,
                        m3u_entries=[],
                        client=client,
                    ),
                )
        except (XtreamError, Exception) as exc:  # noqa: BLE001
            self.after(0, lambda: self._on_connect_fail(str(exc)))

    def _on_connect_fail(self, message: str) -> None:
        self._set_login_loading(False)
        self._login_error.configure(text=message)
        self._set_status("Connection failed", "")

    def _on_connect_success(
        self,
        mode: str,
        server: str,
        username: str,
        password: str,
        categories: list[Category],
        channels: list[Channel],
        m3u_entries: list[M3UEntry],
        client: XtreamClient | None,
    ) -> None:
        self._set_login_loading(False)
        self._mode = mode
        self._client = client
        self._m3u_entries = m3u_entries
        self._categories = categories
        self._all_channels = channels
        self._selected_category_id = None

        if self._remember_var.get():
            save_config(
                {
                    "remember": True,
                    "server_url": server,
                    "username": username,
                    "password": password,
                }
            )
        else:
            clear_credentials()

        self._build_main(server)
        self._set_status(f"Connected - {len(channels)} channels", "")

    # ------------------------------------------------------------------ Main UI

    def _build_main(self, server: str) -> None:
        self._clear_body()

        root = ctk.CTkFrame(self, fg_color=BRAND_BG, corner_radius=0)
        root.pack(fill="both", expand=True)

        # Top bar
        top = ctk.CTkFrame(root, fg_color=BRAND_SURFACE, height=52, corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        logo_small = self._load_logo(size=(120, 48))
        if logo_small:
            ctk.CTkLabel(top, image=logo_small, text="").pack(side="left", padx=12)
        else:
            ctk.CTkLabel(
                top,
                text="RUSHTV",
                font=ctk.CTkFont(size=20, weight="bold"),
                text_color=BRAND_RED,
            ).pack(side="left", padx=16)

        ctk.CTkLabel(
            top,
            text=server,
            text_color=BRAND_MUTED,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            top,
            text="Logout",
            width=90,
            height=32,
            corner_radius=16,
            fg_color=BRAND_SURFACE_LIGHT,
            hover_color=BRAND_RED,
            command=self._build_login,
        ).pack(side="right", padx=12, pady=10)

        # Content: sidebar | list | player
        content = ctk.CTkFrame(root, fg_color=BRAND_BG, corner_radius=0)
        content.pack(fill="both", expand=True, padx=8, pady=8)
        content.grid_columnconfigure(0, weight=0, minsize=200)
        content.grid_columnconfigure(1, weight=1)
        content.grid_columnconfigure(2, weight=2)
        content.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(content, fg_color=BRAND_SURFACE, corner_radius=12)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(
            sidebar,
            text="Categories",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=BRAND_TEXT,
        ).pack(anchor="w", padx=12, pady=(12, 8))

        self._cat_scroll = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent", corner_radius=0
        )
        self._cat_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        self._cat_buttons: list[ctk.CTkButton] = []
        self._populate_categories()

        # Channel list
        center = ctk.CTkFrame(content, fg_color=BRAND_SURFACE, corner_radius=12)
        center.grid(row=0, column=1, sticky="nsew", padx=6)

        search_row = ctk.CTkFrame(center, fg_color="transparent")
        search_row.pack(fill="x", padx=12, pady=12)
        ctk.CTkLabel(
            search_row,
            text="Channels",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left")
        self._search_entry = ctk.CTkEntry(
            search_row,
            placeholder_text="Search channels...",
            width=200,
            fg_color=BRAND_SURFACE_LIGHT,
            border_color=BRAND_SURFACE_LIGHT,
        )
        self._search_entry.pack(side="right")
        self._search_entry.bind("<KeyRelease>", lambda _e: self._apply_filter())

        self._channel_scroll = ctk.CTkScrollableFrame(
            center, fg_color="transparent", corner_radius=0
        )
        self._channel_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        self._apply_filter()

        # Player panel
        player_panel = ctk.CTkFrame(content, fg_color=BRAND_SURFACE, corner_radius=12)
        player_panel.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        player_panel.pack_propagate(True)

        ctk.CTkLabel(
            player_panel,
            text="Now Playing",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))

        self._now_label = ctk.CTkLabel(
            player_panel,
            text="Select a channel",
            text_color=BRAND_MUTED,
            wraplength=360,
            justify="left",
        )
        self._now_label.pack(anchor="w", padx=12)

        self._video_frame = tk.Frame(player_panel, bg="#000000", highlightthickness=0)
        self._video_frame.pack(fill="both", expand=True, padx=12, pady=12)

        controls = ctk.CTkFrame(player_panel, fg_color="transparent")
        controls.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(
            controls,
            text="Stop",
            width=80,
            corner_radius=16,
            fg_color=BRAND_SURFACE_LIGHT,
            hover_color=BRAND_RED,
            command=self._stop_playback,
        ).pack(side="left", padx=4)
        ctk.CTkLabel(
            controls,
            text="Up/Down: surf channels",
            text_color=BRAND_MUTED,
            font=ctk.CTkFont(size=11),
        ).pack(side="right")

        self._init_player()

        # Status bar
        status = ctk.CTkFrame(root, fg_color=BRAND_SURFACE, height=28, corner_radius=0)
        status.pack(fill="x", side="bottom")
        status.pack_propagate(False)
        self._status_conn = ctk.CTkLabel(
            status, text="", text_color=BRAND_MUTED, font=ctk.CTkFont(size=11)
        )
        self._status_conn.pack(side="left", padx=12)
        self._status_now = ctk.CTkLabel(
            status, text="", text_color=BRAND_TEXT, font=ctk.CTkFont(size=11)
        )
        self._status_now.pack(side="right", padx=12)

    def _populate_categories(self) -> None:
        for btn in self._cat_buttons:
            btn.destroy()
        self._cat_buttons.clear()

        all_btn = ctk.CTkButton(
            self._cat_scroll,
            text=f"All ({len(self._all_channels)})",
            anchor="w",
            height=36,
            corner_radius=10,
            fg_color=BRAND_RED if self._selected_category_id is None else BRAND_SURFACE_LIGHT,
            hover_color=BRAND_RED,
            command=lambda: self._select_category(None),
        )
        all_btn.pack(fill="x", pady=3, padx=4)
        self._cat_buttons.append(all_btn)

        for cat in self._categories:
            if isinstance(cat, Category):
                cat_id, cat_name = cat.category_id, cat.name
            else:
                cat_id, cat_name = cat["category_id"], cat["name"]
            count = sum(1 for ch in self._all_channels if ch.category_id == cat_id)
            btn = ctk.CTkButton(
                self._cat_scroll,
                text=f"{cat_name} ({count})",
                anchor="w",
                height=36,
                corner_radius=10,
                fg_color=BRAND_RED if self._selected_category_id == cat_id else BRAND_SURFACE_LIGHT,
                hover_color=BRAND_RED,
                command=lambda cid=cat_id: self._select_category(cid),
            )
            btn.pack(fill="x", pady=3, padx=4)
            self._cat_buttons.append(btn)

    def _select_category(self, category_id: str | None) -> None:
        self._selected_category_id = category_id
        self._populate_categories()
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = ""
        if hasattr(self, "_search_entry"):
            query = self._search_entry.get().strip().lower()

        channels = self._all_channels
        if self._selected_category_id is not None:
            channels = [c for c in channels if c.category_id == self._selected_category_id]
        if query:
            channels = [c for c in channels if query in c.display_name.lower()]

        self._filtered_channels = channels
        self._channel_list_focus = 0
        self._render_channel_list()

    def _render_channel_list(self) -> None:
        for row in self._channel_rows:
            row["frame"].destroy()
        self._channel_rows.clear()

        for index, channel in enumerate(self._filtered_channels):
            row_frame = ctk.CTkFrame(
                self._channel_scroll,
                fg_color=BRAND_SURFACE_LIGHT if index == self._channel_list_focus else "transparent",
                corner_radius=8,
                height=44,
            )
            row_frame.pack(fill="x", pady=2, padx=4)
            row_frame.pack_propagate(False)

            logo = self._image_cache.get(channel.logo)
            ctk.CTkLabel(row_frame, image=logo, text="").pack(side="left", padx=(8, 6), pady=4)

            name_lbl = ctk.CTkLabel(
                row_frame,
                text=channel.display_name,
                anchor="w",
                font=ctk.CTkFont(size=13),
            )
            name_lbl.pack(side="left", fill="x", expand=True, padx=4)

            for widget in (row_frame, name_lbl):
                widget.bind(
                    "<Double-Button-1>",
                    lambda _e, ch=channel, idx=index: self._play_channel(ch, idx),
                )
                widget.bind(
                    "<Button-1>",
                    lambda _e, idx=index: self._focus_channel(idx),
                )

            self._channel_rows.append({"frame": row_frame, "channel": channel})

        if self._current_channel and self._filtered_channels:
            names = [c.stream_id for c in self._filtered_channels]
            if self._current_channel.stream_id in names:
                try:
                    self._channel_list_focus = names.index(self._current_channel.stream_id)
                except ValueError:
                    pass

    def _focus_channel(self, index: int) -> None:
        self._channel_list_focus = max(0, min(index, len(self._filtered_channels) - 1))
        self._render_channel_list()

    # ------------------------------------------------------------------ Playback

    def _init_player(self) -> None:
        try:
            self._player = VLCPlayer(
                on_playing=lambda: self.after(0, self._on_player_playing),
                on_stopped=lambda: self.after(0, self._on_player_stopped),
                on_error=lambda msg: self.after(0, lambda: self._set_status("", msg)),
            )
        except VLCNotFoundError:
            self._player = None
            return
        self.update_idletasks()
        hwnd = self._video_frame.winfo_id()
        self._player.set_window(hwnd)

    def _play_channel(self, channel: Channel, index: int | None = None) -> None:
        if not self._player:
            self._set_status("", "VLC not available")
            return
        if index is not None:
            self._channel_list_focus = index

        try:
            if self._mode == "xtream" and self._client:
                url = self._client.stream_url(channel.stream_id)
            else:
                url = channel_play_url(channel.stream_id, self._m3u_entries)
        except XtreamError as exc:
            self._set_status("", str(exc))
            return

        self._current_channel = channel
        self._now_label.configure(text=channel.display_name)
        self._set_status("", f"Loading: {channel.display_name}")
        self._render_channel_list()
        self._player.play(url)

    def _stop_playback(self) -> None:
        if self._player:
            self._player.stop()
        self._set_status("", "Stopped")

    def _on_player_playing(self) -> None:
        if self._current_channel:
            self._set_status("", f"Playing: {self._current_channel.display_name}")

    def _on_player_stopped(self) -> None:
        if self._current_channel:
            self._set_status("", f"Stopped: {self._current_channel.display_name}")

    def _surf_channel(self, delta: int) -> None:
        if not self._filtered_channels:
            return
        if self._channel_list_focus < 0:
            self._channel_list_focus = 0
        new_index = (self._channel_list_focus + delta) % len(self._filtered_channels)
        channel = self._filtered_channels[new_index]
        self._play_channel(channel, new_index)

    def _on_key_up(self, _event: tk.Event) -> str | None:
        if hasattr(self, "_channel_scroll") and self._player and self._player.is_playing():
            self._surf_channel(-1)
            return "break"
        return None

    def _on_key_down(self, _event: tk.Event) -> str | None:
        if hasattr(self, "_channel_scroll") and self._player and self._player.is_playing():
            self._surf_channel(1)
            return "break"
        return None

    def _on_key_enter(self, _event: tk.Event) -> str | None:
        if not hasattr(self, "_channel_scroll"):
            return None
        if self._filtered_channels and 0 <= self._channel_list_focus < len(self._filtered_channels):
            ch = self._filtered_channels[self._channel_list_focus]
            self._play_channel(ch, self._channel_list_focus)
            return "break"
        return None

    def _on_close(self) -> None:
        if self._player:
            self._player.release()
        self.destroy()


def run_app() -> None:
    app = RushTVApp()
    app.mainloop()
