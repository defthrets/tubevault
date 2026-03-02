#!/usr/bin/env python3
"""
TubeVault - Terminal Video Downloader for Plex
Supports YouTube, Odysee, Vimeo, Twitch, TikTok, and 1000+ sites via yt-dlp
"""

import os
import sys
import json
import re
import time
import signal
import random
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

# ── Dependency bootstrap ──────────────────────────────────────────────────────
def _bootstrap():
    """Auto-install missing Python packages."""
    import subprocess
    needed = []
    for pkg, mod in [("rich", "rich"), ("yt-dlp", "yt_dlp")]:
        try:
            __import__(mod)
        except ImportError:
            needed.append(pkg)
    if needed:
        print(f"\n  [*] Installing required packages: {', '.join(needed)}")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet"] + needed,
            check=True
        )
        print("  [*] Done. Restarting...\n")
        os.execv(sys.executable, [sys.executable] + sys.argv)

_bootstrap()

import yt_dlp
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import (
    Progress, TaskID, BarColumn, TextColumn,
    TimeRemainingColumn, DownloadColumn,
    TransferSpeedColumn, SpinnerColumn
)
from rich.align import Align
from rich.rule import Rule
from rich.live import Live
from rich import box
from rich.markup import escape

console = Console(highlight=False)

# ── Constants ─────────────────────────────────────────────────────────────────
VERSION = "1.0.0"
APP_DIR  = Path.home() / ".config" / "tubevault"
CFG_FILE = APP_DIR / "config.json"
HIST_FILE = APP_DIR / "history.json"

LOGO = r"""
     s                         ..                    _                                          ..      s    
    :8                   . uW8"                     u                                     x .d88"      :8    
   .88       x.    .     `t888                     88Nu.   u.                 x.    .      5888R      .88    
  :888ooo  .@88k  z88u    8888   .        .u      '88888.o888c       u      .@88k  z88u    '888R     :888ooo 
-*8888888 ~"8888 ^8888    9888.z88N    ud8888.     ^8888  8888    us888u.  ~"8888 ^8888     888R   -*8888888 
  8888      8888  888R    9888  888E :888'8888.     8888  8888 .@88 "8888"   8888  888R     888R     8888    
  8888      8888  888R    9888  888E d888 '88%"     8888  8888 9888  9888    8888  888R     888R     8888    
  8888      8888  888R    9888  888E 8888.+"        8888  8888 9888  9888    8888  888R     888R     8888    
 .8888Lu=   8888 ,888B .  9888  888E 8888L         .8888b.888P 9888  9888    8888 ,888B .   888R    .8888Lu= 
 ^%888*    "8888Y 8888"  .8888  888" '8888c. .+     ^Y8888*""  9888  9888   "8888Y 8888"   .888B .  ^%888*   
   'Y"      `Y"   'YP     `%888*%"    "88888%         `Y"      "888*""888"   `Y"   'YP     ^*888%     'Y"    
                             "`         "YP'                    ^Y"   ^Y'                    "%
"""

# Blue → Orange gradient that cycles (used for logo animation + static display)
LOGO_GRADIENT = [
    "#1040ff",  # deep blue
    "#0060ee",
    "#0080dd",
    "#009ecc",
    "#00b2bb",
    "#00c499",
    "#30cc66",
    "#70be30",
    "#aaa800",
    "#d88800",
    "#f86200",
    "#ff3800",  # deep orange
    "#ff5500",
    "#f87000",
    "#d89200",
    "#aaaa00",
    "#70be30",
    "#30cc66",
    "#00c499",
    "#00b2bb",
    "#009ecc",
    "#0080dd",
]

_first_header = True

DEFAULT_CFG: dict = {
    "plex_base":       "/mnt/plex",
    "movies_dir":      "Movies",
    "tv_dir":          "TV Shows",
    "youtube_dir":     "YouTube",
    "prefer_mp4":      True,
    "embed_subs":      True,
    "embed_thumbnail": True,
    "write_nfo":       True,   # Write .nfo file with description (Plex summary)
    "embed_metadata":  True,   # Embed title/description/date into MP4 tags
}

QUALITIES: dict = {
    "1": ("Best Available",    "bestvideo+bestaudio/best",                                       False),
    "2": ("4K  (2160p)",       "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best", False),
    "3": ("1080p",             "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best", False),
    "4": ("720p",              "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best",   False),
    "5": ("480p",              "bestvideo[height<=480]+bestaudio/best",                          False),
    "6": ("360p",              "bestvideo[height<=360]+bestaudio/best",                          False),
    "7": ("Audio Only (MP3)",  "bestaudio/best",                                                 True),
}

CONTENT_TYPES: dict = {
    "1": "Movie",
    "2": "TV Show",
    "3": "YouTube / General",
}

POPULAR_SITES = [
    ("YouTube",    "youtube.com"),
    ("Odysee",     "odysee.com"),
    ("Vimeo",      "vimeo.com"),
    ("Twitch",     "twitch.tv"),
    ("TikTok",     "tiktok.com"),
    ("Twitter/X",  "x.com"),
    ("Reddit",     "reddit.com"),
    ("Rumble",     "rumble.com"),
    ("Dailymotion","dailymotion.com"),
    ("BitChute",   "bitchute.com"),
    ("PeerTube",   "peertube.*"),
    ("Soundcloud", "soundcloud.com"),
    ("BandCamp",   "bandcamp.com"),
    ("Facebook",   "facebook.com"),
    ("Instagram",  "instagram.com"),
    ("Bilibili",   "bilibili.com"),
    ("Niconico",   "nicovideo.jp"),
    ("Crunchyroll","crunchyroll.com"),
    ("Pornhub",    "pornhub.com"),
    ("LBRY",       "lbry.tv"),
]

# ── Config helpers ────────────────────────────────────────────────────────────
def load_cfg() -> dict:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if CFG_FILE.exists():
        try:
            saved = json.loads(CFG_FILE.read_text())
            return {**DEFAULT_CFG, **saved}
        except Exception:
            pass
    CFG_FILE.write_text(json.dumps(DEFAULT_CFG, indent=2))
    return DEFAULT_CFG.copy()

def save_cfg(cfg: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CFG_FILE.write_text(json.dumps(cfg, indent=2))

# ── History helpers ───────────────────────────────────────────────────────────
def load_hist() -> list:
    if HIST_FILE.exists():
        try:
            return json.loads(HIST_FILE.read_text())
        except Exception:
            pass
    return []

def push_hist(entry: dict) -> None:
    hist = load_hist()
    hist.insert(0, entry)
    HIST_FILE.write_text(json.dumps(hist[:200], indent=2))

# ── UI helpers ────────────────────────────────────────────────────────────────
def clr() -> None:
    os.system("clear")

# ── Glitch logo animation ────────────────────────────────────────────────────
GLITCH_CHARS = list("#$%&@*+=-:/\\|<>▓▒░█")
GLITCH_CHANCE = 0.12  # chance per frame to glitch
NOISE_RATE = 0.006    # per-char noise when glitching
JITTER_MAX = 1        # horizontal jitter max
SCANLINE_CHANCE = 0.05
CHANNEL_SPLIT_CHANCE = 0.08
COLOR_SHIFT_RATE = 10 # slow gradient drift
LOGO_LINES = LOGO.splitlines()
LOGO_HEIGHT = len(LOGO_LINES)
_anim_thread: Optional[threading.Thread] = None
_anim_stop = threading.Event()
_anim_pause = threading.Event()
_anim_lock = threading.Lock()

def _glitch_logo_frame(frame: int) -> Text:
    """Build a mostly-stable logo with occasional subtle glitches."""
    rnd = random.Random(frame * 9176 + 1337)
    text = Text()
    n_grad = len(LOGO_GRADIENT)
    is_glitch = rnd.random() < GLITCH_CHANCE
    drift = frame // COLOR_SHIFT_RATE

    for i, raw in enumerate(LOGO_LINES):
        jitter = rnd.randint(-JITTER_MAX, JITTER_MAX) if is_glitch else 0
        line = (" " * max(0, jitter)) + raw + (" " * max(0, -jitter))

        scanline_dim = is_glitch and (rnd.random() < SCANLINE_CHANCE)
        base_color = LOGO_GRADIENT[(i + drift) % n_grad]

        for j, ch in enumerate(line):
            if is_glitch and ch != " " and rnd.random() < NOISE_RATE:
                ch = rnd.choice(GLITCH_CHARS)

            if is_glitch and ch != " " and (rnd.random() < CHANNEL_SPLIT_CHANCE):
                style = "bold red" if (j + frame) % 2 == 0 else "bold blue"
            else:
                style = base_color

            if scanline_dim:
                style = f"dim {style}"

            text.append(ch, style=style)

        text.append("\n")

    return text

def _draw_logo_frame(frame: int) -> None:
    """Render the current frame at the top of the terminal without moving cursor."""
    logo = _glitch_logo_frame(frame)
    with console.capture() as cap:
        console.print(logo, end="")
    rendered = cap.get()
    sys.stdout.write("\x1b7\x1b[H" + rendered + "\x1b8")
    sys.stdout.flush()

def _anim_loop() -> None:
    frame = 0
    while not _anim_stop.is_set():
        if _anim_pause.is_set():
            time.sleep(0.05)
            continue
        with _anim_lock:
            _draw_logo_frame(frame)
        frame += 1
        time.sleep(1 / 12)

def _start_anim() -> None:
    global _anim_thread
    if _anim_thread and _anim_thread.is_alive():
        return
    _anim_stop.clear()
    _anim_pause.clear()
    _anim_thread = threading.Thread(target=_anim_loop, daemon=True)
    _anim_thread.start()

def _pause_anim() -> None:
    _anim_pause.set()

def _resume_anim() -> None:
    _anim_pause.clear()

def ask(*args, **kwargs):
    _pause_anim()
    try:
        return Prompt.ask(*args, **kwargs)
    finally:
        _resume_anim()

def confirm(*args, **kwargs):
    _pause_anim()
    try:
        return Confirm.ask(*args, **kwargs)
    finally:
        _resume_anim()

def header() -> None:
    global _first_header
    clr()
    if _first_header:
        _first_header = False
    _start_anim()
    # Reserve space below the animated logo
    console.print("\n" * (LOGO_HEIGHT + 1), end="")
    console.print(Align.center("[dim]vibecoded by spitmux[/dim]"))
    console.print()
    console.print(
        Align.center(
            f"[dim]Terminal Video Downloader for Plex  ·  v{VERSION}  ·  yt-dlp backend[/dim]"
        )
    )
    console.print(
        Align.center(
            "[dim #0099cc]YouTube · Odysee · Vimeo · Twitch · TikTok · Twitter/X · Rumble · 1000+ sites[/dim #0099cc]"
        )
    )
    console.print()

def rule(title: str = "") -> None:
    console.print(Rule(title, style="#0044bb dim"))

def ok(msg: str)   -> None: console.print(f"  [bold green]✔[/bold green]  {msg}")
def err(msg: str)  -> None: console.print(f"  [bold red]✖[/bold red]  {msg}")
def info(msg: str) -> None: console.print(f"  [bold #0099ff]ℹ[/bold #0099ff]  {msg}")
def warn(msg: str) -> None: console.print(f"  [bold yellow]⚠[/bold yellow]  {msg}")

def pause() -> None:
    console.print()
    ask("[dim]  Press Enter to continue[/dim]", default="", show_default=False)

def safe_name(s: str) -> str:
    """Strip characters illegal in Linux filenames."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', s).strip()

def _xml_escape(s: str) -> str:
    """Escape special characters for XML."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))

def write_nfo(template: str, meta: dict, ctype: str, cfg: dict) -> None:
    """Write a Plex-compatible .nfo file so the description appears as the summary."""
    if not cfg.get("write_nfo", True):
        return

    title       = str(meta.get("title")    or meta.get("id") or "Unknown")
    description = str(meta.get("description") or "")
    uploader    = str(meta.get("uploader") or meta.get("channel") or "")
    upload_date = str(meta.get("upload_date") or "")
    year        = upload_date[:4] if len(upload_date) >= 4 else ""

    # Resolve %(title)s then any remaining yt-dlp tokens, then swap extension → .nfo
    resolved = template.replace("%(title)s", safe_name(title))
    resolved = re.sub(r'%\([^)]+\)s', 'Unknown', resolved)
    nfo_path = re.sub(r'\.[^./]+$', '.nfo', resolved)

    t  = _xml_escape(title)
    d  = _xml_escape(description[:4000])
    u  = _xml_escape(uploader)
    yr = f"  <year>{year}</year>\n" if year else ""

    if ctype == "TV Show":
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<episodedetails>\n'
            f'  <title>{t}</title>\n'
            f'  <plot>{d}</plot>\n'
            f'{yr}'
            '</episodedetails>'
        )
    else:  # Movie or YouTube / General
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<movie>\n'
            f'  <title>{t}</title>\n'
            f'  <plot>{d}</plot>\n'
            f'  <studio>{u}</studio>\n'
            f'{yr}'
            '</movie>'
        )

    try:
        Path(nfo_path).write_text(xml, encoding="utf-8")
        ok(f"NFO saved  →  [dim]{nfo_path}[/dim]")
    except Exception as e:
        warn(f"Could not write NFO: {e}")

# ── Main menu ─────────────────────────────────────────────────────────────────
def main_menu() -> str:
    header()
    t = Table(
        show_header=False, box=box.SIMPLE, border_style="#003388 dim",
        padding=(0, 3), show_edge=False,
    )
    t.add_column(style="bold orange1", no_wrap=True)
    t.add_column(style="white")
    t.add_row("[ 1 ]", "Download Video or Playlist")
    t.add_row("[ 2 ]", "Batch Download  (from URL list file)")
    t.add_row("[ 3 ]", "View Download History")
    t.add_row("[ 4 ]", "Settings")
    t.add_row("[ 5 ]", "Update yt-dlp")
    t.add_row("[ 6 ]", "Supported Sites")
    t.add_row("[ Q ]", "Quit")

    console.print(Panel(
        Align.center(t),
        title="[bold #0099ff]  MAIN MENU  [/bold #0099ff]",
        border_style="#0066cc",
        padding=(1, 6),
    ))
    console.print()
    return ask("  [bold #0099ff]Select[/bold #0099ff]", default="Q").strip().upper()

# ── Video info ────────────────────────────────────────────────────────────────
def get_info(url: str) -> Optional[dict]:
    opts = {"quiet": True, "no_warnings": True, "skip_download": True,
            "extract_flat": "in_playlist"}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        err(f"Could not fetch info: {escape(str(e))}")
        return None

def show_info(info: dict) -> None:
    is_playlist = info.get("_type") == "playlist"

    if is_playlist:
        entries  = [e for e in (info.get("entries") or []) if e]
        title    = info.get("title", "Unknown Playlist")
        uploader = info.get("uploader") or info.get("channel", "Unknown")
        t = Table(show_header=False, box=box.SIMPLE, border_style="dim", padding=(0, 1))
        t.add_column(style="bold #0099ff", no_wrap=True, width=14)
        t.add_column(style="white")
        t.add_row("Playlist",  escape(title[:80]))
        t.add_row("Channel",   escape(str(uploader)))
        t.add_row("Videos",    str(len(entries)))
        console.print(Panel(t, title="[bold orange1]  PLAYLIST  [/bold orange1]", border_style="orange1"))
    else:
        title      = info.get("title", "Unknown")
        uploader   = info.get("uploader") or info.get("channel", "Unknown")
        duration   = info.get("duration")
        view_count = info.get("view_count")
        upload_date = info.get("upload_date", "")

        dur_str = ""
        if duration:
            m, s = divmod(int(duration), 60)
            h, m = divmod(m, 60)
            dur_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

        date_str = ""
        if upload_date:
            try:
                date_str = datetime.strptime(upload_date, "%Y%m%d").strftime("%B %d, %Y")
            except Exception:
                pass

        t = Table(show_header=False, box=box.SIMPLE, border_style="dim", padding=(0, 1))
        t.add_column(style="bold #0099ff", no_wrap=True, width=14)
        t.add_column(style="white")
        t.add_row("Title",    escape(str(title)[:80]))
        t.add_row("Uploader", escape(str(uploader)))
        if dur_str:       t.add_row("Duration",  dur_str)
        if date_str:      t.add_row("Uploaded",  date_str)
        if view_count:    t.add_row("Views",      f"{view_count:,}")
        console.print(Panel(t, title="[bold green]  VIDEO INFO  [/bold green]", border_style="green"))

# ── Quality selection ─────────────────────────────────────────────────────────
def quality_menu() -> tuple:
    """Returns (label, format_string, audio_only)."""
    t = Table(
        show_header=False, box=box.SIMPLE, border_style="#003388 dim",
        padding=(0, 2), show_edge=False,
    )
    t.add_column(style="bold orange1", no_wrap=True)
    t.add_column(style="white")
    for k, (label, _, _) in QUALITIES.items():
        t.add_row(f"[ {k} ]", label)
    console.print(Panel(
        t, title="[bold #0099ff]  SELECT QUALITY  [/bold #0099ff]",
        border_style="#0066cc", padding=(0, 4),
    ))
    console.print()
    ch = ask("  [bold #0099ff]Quality[/bold #0099ff]", default="3").strip()
    return QUALITIES.get(ch, QUALITIES["3"])

# ── Output path builder ───────────────────────────────────────────────────────
def build_output_path(cfg: dict, info: Optional[dict], audio_only: bool) -> tuple:
    """Prompt for content type and return (output_template, content_type)."""
    base     = Path(cfg["plex_base"])
    is_pl    = (info or {}).get("_type") == "playlist"

    t = Table(
        show_header=False, box=box.SIMPLE, border_style="#003388 dim",
        padding=(0, 2), show_edge=False,
    )
    t.add_column(style="bold orange1", no_wrap=True)
    t.add_column(style="white")
    for k, v in CONTENT_TYPES.items():
        t.add_row(f"[ {k} ]", v)
    console.print(Panel(
        t, title="[bold #0099ff]  CONTENT TYPE  [/bold #0099ff]",
        border_style="#0066cc", padding=(0, 4),
    ))
    console.print()
    ct = ask("  [bold #0099ff]Type[/bold #0099ff]", default="3").strip()
    ctype = CONTENT_TYPES.get(ct, "YouTube / General")

    if ctype == "Movie":
        movie_title = ask("  [bold #0099ff]Movie name[/bold #0099ff]")
        year        = ask("  [bold #0099ff]Year[/bold #0099ff]", default="")
        s = safe_name(movie_title)
        folder = f"{s} ({year})" if year else s
        out_dir = base / cfg["movies_dir"] / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        template = str(out_dir / f"{folder}.%(ext)s")

    elif ctype == "TV Show":
        show   = ask("  [bold #0099ff]Show name[/bold #0099ff]")
        season = ask("  [bold #0099ff]Season number[/bold #0099ff]", default="1")
        ep_num = ask("  [bold #0099ff]Starting episode number[/bold #0099ff]", default="1")
        s      = safe_name(show)
        sn     = int(season)
        en     = int(ep_num)
        season_folder = f"Season {sn:02d}"
        out_dir = base / cfg["tv_dir"] / s / season_folder
        out_dir.mkdir(parents=True, exist_ok=True)
        if is_pl:
            template = str(out_dir / f"{s} - S{sn:02d}E%(autonumber)s.%(ext)s")
        else:
            template = str(out_dir / f"{s} - S{sn:02d}E{en:02d}.%(ext)s")

    else:  # YouTube / General
        uploader = (
            (info or {}).get("uploader")
            or (info or {}).get("channel")
            or "Unknown"
        )
        s = safe_name(str(uploader)) or "Unknown"
        out_dir = base / cfg["youtube_dir"] / s
        out_dir.mkdir(parents=True, exist_ok=True)
        template = str(out_dir / "%(title)s.%(ext)s")

    return template, ctype

# ── Rich progress hook ────────────────────────────────────────────────────────
class RichProgressHook:
    """yt-dlp progress hook that drives a rich progress bar."""

    def __init__(self):
        self._prog = Progress(
            SpinnerColumn(style="#0099ff"),
            TextColumn("[bold #0099ff]{task.description}[/]"),
            BarColumn(bar_width=38, style="dim #0044bb", complete_style="bold orange1"),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "·",
            DownloadColumn(),
            "·",
            TransferSpeedColumn(),
            "·",
            TimeRemainingColumn(),
            console=console,
            transient=False,
        )
        self._task: Optional[TaskID] = None
        self._live = False

    def hook(self, d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            total      = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            fn         = Path(d.get("filename", "")).name
            desc       = escape(fn[:55])
            if not self._live:
                self._prog.start()
                self._task = self._prog.add_task(desc, total=total or 100)
                self._live = True
            if self._task is not None:
                self._prog.update(self._task, completed=downloaded,
                                  total=total or 100, description=desc)
        elif status == "finished":
            if self._live and self._task is not None:
                self._prog.update(self._task,
                                  completed=self._prog.tasks[self._task].total or 0)
            self._stop()
        elif status == "error":
            self._stop()

    def _stop(self) -> None:
        if self._live:
            self._prog.stop()
            self._live = False

    def stop(self) -> None:
        self._stop()

# ── Core download ─────────────────────────────────────────────────────────────
def do_download(url: str, cfg: dict, fmt: str, template: str,
                audio_only: bool) -> bool:
    rp = RichProgressHook()

    postprocessors = []
    if audio_only:
        postprocessors.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        })
    if cfg.get("embed_metadata", True):
        postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
    if cfg.get("embed_subs") and not audio_only:
        postprocessors.append({"key": "FFmpegEmbedSubtitle"})
    if cfg.get("embed_thumbnail"):
        postprocessors.append({"key": "EmbedThumbnail"})

    ydl_opts: dict = {
        "format":               fmt,
        "outtmpl":              template,
        "progress_hooks":       [rp.hook],
        "quiet":                True,
        "no_warnings":          True,
        "postprocessors":       postprocessors,
        "writethumbnail":       cfg.get("embed_thumbnail", False),
        "writesubtitles":       cfg.get("embed_subs", False) and not audio_only,
        "writeautomaticsub":    cfg.get("embed_subs", False) and not audio_only,
        "subtitleslangs":       ["en"],
        "merge_output_format":  "mp4" if cfg.get("prefer_mp4") and not audio_only else None,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        rp.stop()
        return True
    except yt_dlp.utils.DownloadError as e:
        rp.stop()
        err(f"Download error: {escape(str(e)[:200])}")
        return False
    except Exception as e:
        rp.stop()
        err(f"Unexpected error: {escape(str(e)[:200])}")
        return False

# ── Download workflow ─────────────────────────────────────────────────────────
def download_flow(cfg: dict, url: Optional[str] = None) -> None:
    header()
    rule("  DOWNLOAD  ")
    console.print()

    if not url:
        url = ask("  [bold #0099ff]Enter URL[/bold #0099ff]").strip()
    if not url:
        warn("No URL provided.")
        pause()
        return

    console.print()
    with console.status("[#0099ff]Fetching video information...[/#0099ff]", spinner="dots"):
        meta = get_info(url)
    if not meta:
        pause()
        return

    console.print()
    show_info(meta)
    console.print()

    ql, fmt, audio_only = quality_menu()
    console.print()

    template, ctype = build_output_path(cfg, meta, audio_only)
    console.print()

    # Confirmation panel
    ct = Table(show_header=False, box=box.SIMPLE, border_style="dim", padding=(0, 1))
    ct.add_column(style="bold #0099ff", width=14)
    ct.add_column(style="white")
    ct.add_row("Quality",  ql)
    ct.add_row("Type",     ctype)
    ct.add_row("Save to",  str(Path(template).parent))
    console.print(Panel(ct, title="[bold white]  CONFIRM  [/bold white]",
                        border_style="white", padding=(0, 2)))
    console.print()

    if not confirm("  [bold #0099ff]Start download?[/bold #0099ff]", default=True):
        warn("Cancelled.")
        pause()
        return

    console.print()
    rule("  DOWNLOADING  ")
    console.print()

    started = datetime.now()
    success = do_download(url, cfg, fmt, template, audio_only)
    elapsed = int((datetime.now() - started).total_seconds())

    console.print()
    title_str = str(meta.get("title") or meta.get("id") or "Unknown")[:80]

    if success:
        ok(f"Complete!  ({elapsed}s)  →  [dim]{Path(template).parent}[/dim]")
        write_nfo(template, meta, ctype, cfg)
    else:
        err("Download failed.")

    push_hist({
        "url":     url,
        "title":   title_str,
        "type":    ctype,
        "quality": ql,
        "path":    str(Path(template).parent),
        "date":    datetime.now().isoformat(timespec="seconds"),
        "success": success,
    })
    pause()

# ── Batch download ────────────────────────────────────────────────────────────
def batch_flow(cfg: dict) -> None:
    header()
    rule("  BATCH DOWNLOAD  ")
    console.print()
    info("Provide a text file with one URL per line. Lines starting with # are ignored.")
    console.print()

    filepath = ask("  [bold #0099ff]URL list file[/bold #0099ff]").strip()
    fp = Path(filepath)
    if not fp.exists():
        err(f"File not found: {fp}")
        pause()
        return

    urls = [
        line.strip()
        for line in fp.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not urls:
        warn("No URLs found in file.")
        pause()
        return

    info(f"Found {len(urls)} URL(s).")
    console.print()

    ql, fmt, audio_only = quality_menu()
    console.print()

    info("Output path applies to all downloads in this batch.")
    template, ctype = build_output_path(cfg, None, audio_only)
    console.print()

    if not confirm(f"  [bold #0099ff]Download {len(urls)} video(s)?[/bold #0099ff]", default=True):
        warn("Cancelled.")
        pause()
        return

    console.print()
    ok_count = 0
    for i, url in enumerate(urls, 1):
        rule(f"  [{i}/{len(urls)}]  ")
        console.print(f"  [dim]{escape(url[:100])}[/dim]")
        console.print()
        success = do_download(url, cfg, fmt, template, audio_only)
        if success:
            ok_count += 1
            ok("Done")
        else:
            err("Failed")
        console.print()

    rule()
    ok(f"Batch complete: [bold green]{ok_count}[/bold green]/[bold]{len(urls)}[/bold] succeeded.")
    pause()

# ── History ───────────────────────────────────────────────────────────────────
def history_view() -> None:
    header()
    rule("  DOWNLOAD HISTORY  ")
    console.print()

    hist = load_hist()
    if not hist:
        warn("No download history yet.")
        pause()
        return

    t = Table(
        box=box.SIMPLE_HEAVY, border_style="#003388 dim",
        header_style="bold #0099ff", show_lines=False, padding=(0, 1),
    )
    t.add_column("#",       style="dim",         width=4,  justify="right")
    t.add_column("Date",    style="dim white",   width=19, no_wrap=True)
    t.add_column("Title",   style="white",       max_width=44)
    t.add_column("Type",    style="#0099ff",      width=13)
    t.add_column("Quality", style="orange1",      width=16)
    t.add_column("Status",  justify="center",     width=8)

    for i, h in enumerate(hist[:60], 1):
        date_str = h.get("date", "")[:19].replace("T", " ")
        status   = "[bold green]✔ OK[/bold green]" if h.get("success") else "[bold red]✖ FAIL[/bold red]"
        title    = escape(h.get("title", "Unknown")[:44])
        t.add_row(str(i), date_str, title, h.get("type","?"), h.get("quality","?"), status)

    console.print(t)
    console.print(f"  [dim]Showing {min(len(hist), 60)} of {len(hist)} entries  ·  stored in {HIST_FILE}[/dim]")
    console.print()

    if confirm("  [bold red]Clear all history?[/bold red]", default=False):
        HIST_FILE.write_text("[]")
        ok("History cleared.")
        time.sleep(0.6)

# ── Settings ──────────────────────────────────────────────────────────────────
def settings_menu() -> None:
    while True:
        cfg = load_cfg()
        header()
        rule("  SETTINGS  ")
        console.print()

        t = Table(
            show_header=False, box=box.SIMPLE, border_style="#003388 dim",
            padding=(0, 2), show_edge=False,
        )
        t.add_column(style="bold orange1", no_wrap=True, width=8)
        t.add_column(style="#0099ff",      width=22)
        t.add_column(style="white")

        t.add_row("[ 1 ]", "Plex base path",    cfg["plex_base"])
        t.add_row("[ 2 ]", "Movies folder",     cfg["movies_dir"])
        t.add_row("[ 3 ]", "TV Shows folder",   cfg["tv_dir"])
        t.add_row("[ 4 ]", "YouTube folder",    cfg["youtube_dir"])
        t.add_row("[ 5 ]", "Prefer MP4",          "[green]Yes[/green]" if cfg["prefer_mp4"]       else "[red]No[/red]")
        t.add_row("[ 6 ]", "Embed subtitles",    "[green]Yes[/green]" if cfg["embed_subs"]        else "[red]No[/red]")
        t.add_row("[ 7 ]", "Embed thumbnail",    "[green]Yes[/green]" if cfg["embed_thumbnail"]   else "[red]No[/red]")
        t.add_row("[ 8 ]", "Write NFO / summary","[green]Yes[/green]" if cfg.get("write_nfo",True) else "[red]No[/red]")
        t.add_row("[ 9 ]", "Embed metadata tags","[green]Yes[/green]" if cfg.get("embed_metadata",True) else "[red]No[/red]")
        t.add_row()
        t.add_row("[ B ]", "Back / Save",        "")

        console.print(Panel(t, title="[bold #0099ff]  CONFIGURATION  [/bold #0099ff]",
                            border_style="#0066cc", padding=(1, 2)))
        console.print()

        ch = ask("  [bold #0099ff]Select[/bold #0099ff]", default="B").strip().upper()

        if   ch == "1": cfg["plex_base"]       = ask("  Plex base path",    default=cfg["plex_base"])
        elif ch == "2": cfg["movies_dir"]       = ask("  Movies folder",     default=cfg["movies_dir"])
        elif ch == "3": cfg["tv_dir"]           = ask("  TV Shows folder",   default=cfg["tv_dir"])
        elif ch == "4": cfg["youtube_dir"]      = ask("  YouTube folder",    default=cfg["youtube_dir"])
        elif ch == "5": cfg["prefer_mp4"]       = confirm("  Prefer MP4?",      default=cfg["prefer_mp4"])
        elif ch == "6": cfg["embed_subs"]       = confirm("  Embed subtitles?", default=cfg["embed_subs"])
        elif ch == "7": cfg["embed_thumbnail"]  = confirm("  Embed thumbnail?",       default=cfg["embed_thumbnail"])
        elif ch == "8": cfg["write_nfo"]        = confirm("  Write NFO / summary?",   default=cfg.get("write_nfo", True))
        elif ch == "9": cfg["embed_metadata"]   = confirm("  Embed metadata in file?", default=cfg.get("embed_metadata", True))
        elif ch == "B":
            save_cfg(cfg)
            ok("Settings saved.")
            time.sleep(0.6)
            break

        save_cfg(cfg)

# ── Update yt-dlp ─────────────────────────────────────────────────────────────
def update_ytdlp() -> None:
    import subprocess
    header()
    rule("  UPDATE yt-dlp  ")
    console.print()
    with console.status("[#0099ff]Updating yt-dlp via pip...[/#0099ff]", spinner="dots"):
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", "yt-dlp"],
            capture_output=True, text=True,
        )
    if result.returncode == 0:
        ok("yt-dlp updated successfully.")
        try:
            ver = yt_dlp.version.__version__
            info(f"Version: {ver}")
        except Exception:
            pass
    else:
        err("Update failed.")
        if result.stderr:
            console.print(f"[dim]{escape(result.stderr[:400])}[/dim]")
    pause()

# ── Supported sites ───────────────────────────────────────────────────────────
def show_sites() -> None:
    header()
    rule("  POPULAR SUPPORTED SITES  ")
    console.print()

    cols = 4
    rows = (len(POPULAR_SITES) + cols - 1) // cols
    t = Table(show_header=False, box=box.SIMPLE, border_style="#003388 dim",
              padding=(0, 3), show_edge=False)
    for _ in range(cols):
        t.add_column(style="#0099ff", no_wrap=True)

    for r in range(rows):
        row_items = []
        for c in range(cols):
            idx = r + c * rows
            if idx < len(POPULAR_SITES):
                name, domain = POPULAR_SITES[idx]
                row_items.append(f"[bold white]{name}[/bold white] [dim]{domain}[/dim]")
            else:
                row_items.append("")
        t.add_row(*row_items)

    console.print(t)
    console.print()
    info("yt-dlp supports 1000+ sites. Full list: [#0099ff]yt-dlp --list-extractors[/#0099ff]")
    pause()

# ── Signal handler ────────────────────────────────────────────────────────────
def _sig_handler(sig, frame) -> None:
    console.print("\n\n  [bold orange1]Interrupted. Goodbye![/bold orange1]\n")
    sys.exit(0)

signal.signal(signal.SIGINT, _sig_handler)

# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    cfg = load_cfg()

    # Handle URL passed as CLI argument
    if len(sys.argv) > 1:
        url_arg = sys.argv[1]
        header()
        console.print(f"  [dim]URL: {escape(url_arg)}[/dim]\n")
        download_flow(cfg, url=url_arg)
        return

    while True:
        choice = main_menu()

        if   choice == "1": download_flow(cfg)
        elif choice == "2": batch_flow(cfg)
        elif choice == "3": history_view()
        elif choice == "4":
            settings_menu()
            cfg = load_cfg()
        elif choice == "5": update_ytdlp()
        elif choice == "6": show_sites()
        elif choice in ("Q", "QUIT", "EXIT"):
            header()
            console.print(Align.center("[bold orange1]Thanks for using TubeVault!  Goodbye.[/bold orange1]"))
            console.print()
            sys.exit(0)

if __name__ == "__main__":
    main()






