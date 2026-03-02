# VidGrab — Terminal Video Downloader for Plex

```
 ██╗   ██╗██╗██████╗  ██████╗ ██████╗  █████╗ ██████╗
 ██║   ██║██║██╔══██╗██╔════╝ ██╔══██╗██╔══██╗██╔══██╗
 ██║   ██║██║██║  ██║██║  ███╗██████╔╝███████║██████╔╝
 ╚██╗ ██╔╝██║██║  ██║██║   ██║██╔══██╗██╔══██║██╔══██╗
  ╚████╔╝ ██║██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝
   ╚═══╝  ╚═╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝
```

Terminal-based video downloader for Debian 13 servers running Plex.
Supports **YouTube, Odysee, Vimeo, Twitch, TikTok, Twitter/X, Rumble** and 1000+ sites via **yt-dlp**.

---

## Requirements

- Debian 13 (Trixie) or Ubuntu 22.04+
- Python 3.11+
- ffmpeg
- Internet connection

---

## Installation

```bash
git clone <repo> vidgrab
cd vidgrab
chmod +x install.sh
sudo ./install.sh
```

The installer will:

1. Install `python3`, `python3-venv`, `ffmpeg`, `atomicparsley` via apt
2. Create a virtual environment at `/opt/vidgrab/venv`
3. Install `rich` and `yt-dlp` Python packages
4. Place a `vidgrab` command in `/usr/local/bin`
5. Create your Plex media directories
6. Write a default config to `~/.config/vidgrab/config.json`

---

## Usage

### Interactive menu
```bash
vidgrab
```

### Direct URL (skip menu)
```bash
vidgrab 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
vidgrab 'https://odysee.com/@channel/video-slug'
```

### Batch download from file
```bash
# Create a file with one URL per line:
cat > urls.txt << EOF
https://youtube.com/watch?v=abc123
https://odysee.com/@mychannel/some-video
# This line is a comment and will be skipped
https://vimeo.com/123456789
EOF

vidgrab   # Select option 2
```

---

## Menu Options

| Option | Description |
|--------|-------------|
| **1** | Download single video or playlist |
| **2** | Batch download from URL list file |
| **3** | View download history (last 200 entries) |
| **4** | Settings (paths, quality, subtitles) |
| **5** | Update yt-dlp to latest version |
| **6** | Show popular supported sites |
| **Q** | Quit |

---

## Quality Options

| # | Quality |
|---|---------|
| 1 | Best available |
| 2 | 4K (2160p) |
| 3 | 1080p (default) |
| 4 | 720p |
| 5 | 480p |
| 6 | 360p |
| 7 | Audio only (MP3 192kbps) |

---

## Plex Folder Structure

VidGrab organises downloads to match Plex's expected library structure:

```
/mnt/plex/
├── Movies/
│   └── Inception (2010)/
│       └── Inception (2010).mp4
├── TV Shows/
│   └── Breaking Bad/
│       └── Season 01/
│           └── Breaking Bad - S01E01.mp4
└── YouTube/
    └── Veritasium/
        └── Why Gravity is NOT a Force.mp4
```

Add these as separate Plex libraries:

- **Movies** → `/mnt/plex/Movies`
- **TV Shows** → `/mnt/plex/TV Shows`
- **Home Videos** (or YouTube) → `/mnt/plex/YouTube`

---

## Configuration

Config file: `~/.config/vidgrab/config.json`

```json
{
  "plex_base":       "/mnt/plex",
  "movies_dir":      "Movies",
  "tv_dir":          "TV Shows",
  "youtube_dir":     "YouTube",
  "prefer_mp4":      true,
  "embed_subs":      true,
  "embed_thumbnail": true
}
```

Edit via the Settings menu (`vidgrab` → option 4) or directly in the file.

---

## Features

- **Rich TUI** — coloured panels, progress bars, spinners
- **Video info preview** — title, uploader, duration, views before download
- **Plex-ready naming** — correct folder/filename conventions for Movies and TV
- **Subtitle embedding** — auto-fetches and embeds English subs (when available)
- **Thumbnail embedding** — embeds video thumbnail into MP4/MP3
- **Download history** — keeps last 200 entries with status
- **Batch mode** — feed a text file of URLs, one per line
- **CLI shortcut** — pass URL directly: `vidgrab '<url>'`
- **Self-updating** — option 5 upgrades yt-dlp in place

---

## Updating VidGrab

To update yt-dlp (the download engine), run:

```bash
vidgrab   # Select option 5
```

To update VidGrab itself, pull the latest code and re-copy:

```bash
cp vidgrab.py /opt/vidgrab/vidgrab.py
```

---

## Uninstall

```bash
sudo rm -rf /opt/vidgrab
sudo rm /usr/local/bin/vidgrab
rm -rf ~/.config/vidgrab
```
