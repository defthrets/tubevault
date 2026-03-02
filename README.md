# VidGrab — Terminal Video Downloader for Plex

```
   _            .       ..                                                  ..
  u            @88>   dF                                              . uW8"
 88Nu.   u.    %8P   '88bu.                     .u    .               `t888
'88888.o888c    .    '*88888bu        uL      .d88B :@8c        u      8888   .
 ^8888  8888  .@88u    ^"*8888N   .ue888Nc.. ="8888f8888r    us888u.   9888.z88N
  8888  8888 ''888E`  beWE "888L d88E`"888E`   4888>'88"  .@88 "8888"  9888  888E
  8888  8888   888E   888E  888E 888E  888E    4888> '    9888  9888   9888  888E
  8888  8888   888E   888E  888E 888E  888E    4888>      9888  9888   9888  888E
 .8888b.888P   888E   888E  888F 888E  888E   .d888L .+   9888  9888   9888  888E
  ^Y8888*""    888&  .888N..888  888& .888E   ^"8888*"    9888  9888  .8888  888"
    `Y"        R888"  `"888*""   *888" 888&      "Y"      "888*""888"  `%888*%"
                ""       ""       `"   "888E               ^Y"   ^Y'      "`
                                 .dWi   `88E
                                 4888~  J8%
                                  ^"===*"`

                       vibecoded by spitmux
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

> ⚠️ **If you downloaded the files on Windows** and are running on Linux, fix line endings first:
> ```bash
> sed -i 's/\r//' install.sh vidgrab.py
> chmod +x install.sh
> sudo ./install.sh
> ```

The installer will:

1. Install `python3`, `python3-venv`, `ffmpeg`, `atomicparsley` via apt
2. Create a virtual environment at `/opt/vidgrab/venv`
3. Install `rich` and `yt-dlp` Python packages
4. Place a `vidgrab` command in `/usr/local/bin`
5. Create your Plex media directories (`Movies`, `TV Shows`, `YouTube`)
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
# Create a file with one URL per line (# = comment):
cat > urls.txt << EOF
https://youtube.com/watch?v=abc123
https://odysee.com/@mychannel/some-video
# This line is skipped
https://vimeo.com/123456789
EOF

vidgrab   # Select option 2
```

### Update script on server
```bash
# From Windows:
scp C:\vidgrab\vidgrab.py user@server:~/vidgrab.py
ssh -t user@server "sudo mv ~/vidgrab.py /opt/vidgrab/vidgrab.py"
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
/srv/media/
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

---

## Plex Library Setup

### Library types

| Folder | Plex Library Type |
|--------|-------------------|
| `YouTube/` | **Home Videos** (UK: "Other Videos") |
| `Movies/` | **Movies** |
| `TV Shows/` | **TV Shows** |

> ⚠️ Do **not** use "Movies" type for YouTube content — Plex will try to match filenames against its online database and show nothing. Use **Home Videos / Other Videos** instead.

### If Plex is running in Docker (linuxserver/plex)

The container can only see paths that are **mounted into it**. Add your media folder as a volume in `docker-compose.yml`:

```yaml
services:
  plex:
    image: lscr.io/linuxserver/plex:latest
    volumes:
      - /srv/docker/plex/config:/config
      - /srv/media/tv:/tv
      - /srv/media/movies:/movies
      - /srv/media/downloads:/downloads
      - /srv/media/YouTube:/youtube      # ← add this
```

Then restart the container:
```bash
cd /srv/docker && docker compose up -d plex
```

And set the Plex library folder to `/youtube` (the **in-container** path, not the host path).

### Pin the library to home screen

Home Video libraries are hidden by default:
> Plex sidebar → hover **"YouTube"** library → click the **📌 pin icon**

---

## Configuration

Config file: `~/.config/vidgrab/config.json`

```json
{
  "plex_base":       "/srv/media",
  "movies_dir":      "Movies",
  "tv_dir":          "TV Shows",
  "youtube_dir":     "YouTube",
  "prefer_mp4":      true,
  "embed_subs":      true,
  "embed_thumbnail": true,
  "write_nfo":       true,
  "embed_metadata":  true
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `write_nfo` | `true` | Write a `.nfo` file alongside each video — Plex reads this for the **summary/plot** |
| `embed_metadata` | `true` | Embed title, description, uploader, date into MP4/MP3 file tags |

Edit via the Settings menu (`vidgrab` → option **4**) or directly in the file.

---

## Features

- **Rich TUI** — blue-to-orange colour scheme, animated logo on startup, progress bars, spinners
- **Video info preview** — title, uploader, duration, views before download
- **Plex-ready naming** — correct folder/filename conventions for Movies and TV
- **Description as Plex summary** — writes a `.nfo` file alongside each video so the description appears as the summary in Plex
- **Embedded metadata** — title, description, uploader, date baked into the MP4/MP3 tags
- **Subtitle embedding** — auto-fetches and embeds English subs (when available)
- **Thumbnail embedding** — embeds video thumbnail into MP4/MP3
- **Download history** — keeps last 200 entries with status
- **Batch mode** — feed a text file of URLs, one per line
- **CLI shortcut** — pass URL directly: `vidgrab '<url>'`
- **Self-updating** — option 5 upgrades yt-dlp in place

---

## Troubleshooting

### `env: 'bash\r': No such file or directory`
Windows CRLF line endings. Fix with:
```bash
sed -i 's/\r//' install.sh vidgrab.py
```

### `TypeError: TextColumn.__init__() got an unexpected keyword argument 'no_wrap'`
Older version of `rich` installed. Fix on the server:
```bash
sudo python3 -c "
f = open('/opt/vidgrab/vidgrab.py', 'r')
t = f.read()
f.close()
t = t.replace('TextColumn(\"[bold cyan]{task.description}[/]\", no_wrap=True, table_column=None)', 'TextColumn(\"[bold cyan]{task.description}[/]\")')
open('/opt/vidgrab/vidgrab.py', 'w').write(t)
print('Done.')
"
```

### `PermissionError` when creating download folders
```bash
sudo chown -R $USER:$USER /srv/media
```

### `chown: invalid user: 'plex:plex'`
Plex is likely running in Docker as your own user — no permission fix needed. Check with:
```bash
ps aux | grep plex
```

### Plex library shows empty after scan
1. Wrong library type — use **Home Videos / Other Videos**, not Movies
2. Plex is in Docker — the host path must be mounted into the container (see Docker section above)
3. Library folder path in Plex must be the **in-container** path (e.g. `/youtube`), not the host path

---

## Updating VidGrab

**Update yt-dlp** (download engine):
```bash
vidgrab   # Select option 5
```

**Update VidGrab itself** from Windows:
```bash
scp C:\vidgrab\vidgrab.py user@server:~/vidgrab.py
ssh -t user@server "sudo mv ~/vidgrab.py /opt/vidgrab/vidgrab.py"
```

---

## Uninstall

```bash
sudo rm -rf /opt/vidgrab
sudo rm /usr/local/bin/vidgrab
rm -rf ~/.config/vidgrab
```
