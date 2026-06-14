# RushTV

Local Windows IPTV player with a dark red/black RushTV theme. Connect with **Xtream Codes** (server URL + username + password) or paste an **M3U / M3U Plus** playlist URL. Playback uses **VLC** embedded in the app window.

## Requirements

- Windows 10 or 11
- [Python 3.10+](https://www.python.org/downloads/) (add Python to PATH during install)
- [VLC media player](https://www.videolan.org/vlc/) (64-bit recommended)

## Quick start (run from source)

```bat
cd RushTV
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Login options

| Mode | What to enter |
|------|----------------|
| Xtream | Server like `http://host:port`, plus username and password |
| M3U URL | Full playlist URL (`.m3u`, `get.php?...type=m3u`, etc.). User/pass optional if the URL embeds them |
| Local M3U | Host the file or use a `file://` path is not supported; use an HTTP URL or Xtream instead |

Credentials can be stored under **Remember me** in `%APPDATA%\RushTV\config.json` on your PC only (never committed to git).

## Build `RushTV.exe` locally

1. Install Python and VLC (above).
2. From the project folder, run:

```bat
build.bat
```

This installs dependencies, runs `scripts\generate_assets.py` to create `assets\logo.png` and `assets\icon.ico` if missing, then builds with PyInstaller.

Output: `dist\RushTV.exe`

> **Note:** VLC must still be installed on the machine where you run the exe; RushTV loads `libvlc` from the standard VLC install paths.

## Branding assets

- Drop your own `assets\logo.png` for the login screen (see `assets\README.txt`).
- `build.bat` generates placeholder branded assets when files are missing.

## Clone and build (for friends)

```bat
git clone https://github.com/brivera2005/RushTV.git
cd RushTV
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
build.bat
```

Share the built `dist\RushTV.exe` or have friends run `python main.py` after cloning.

## Project layout

- `main.py` â€” entry point
- `rushtv/app.py` â€” CustomTkinter UI
- `rushtv/xtream.py` â€” Xtream Codes API
- `rushtv/m3u_parser.py` â€” M3U fetch/parse
- `rushtv/player.py` â€” VLC wrapper
- `rushtv/storage.py` â€” local settings in `%APPDATA%\RushTV`
- `build.bat`, `RushTV.spec` â€” PyInstaller one-file build

## License

Use and modify for personal IPTV playback. You are responsible for complying with your provider's terms and local laws.