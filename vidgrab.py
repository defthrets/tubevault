#!/usr/bin/env python3
"""
VidGrab - Terminal Video Downloader for Plex
Supports YouTube, Odysee, Vimeo, Twitch, TikTok, and 1000+ sites via yt-dlp
"""

import os
import sys
import json
import re
import time
import signal
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
from rich import box
from rich.markup import escape

console = Console(highlight=False)

# ── Constants ─────────────────────────────────────────────────────────────────
VERSION = "1.0.0"
APP_DIR  = Path.home() / ".config" / "vidgrab"
CFG_FILE = APP_DIR / "config.json"
HIST_FILE = APP_DIR / "history.json"

LOGO = r"""
 ██╗   ██╗██╗██████╗  ██████╗ ██████╗  █████╗ ██████╗
 ██║   ██║██║██╔══██╗██╔════╝ ██╔══██╗██╔══██╗██╔══██╗
 ██║   ██║██║██║  ██║██║  ███╗██████╔╝███████║██████╔╝
 ╚██╗ ██╔╝██║██║  ██║██║   ██║██╔══██╗██╔══██║██╔══██╗
  ╚████╔╝ ██║██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝
   ╚═══╝  ╚═╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝"""

DEFAULT_CFG: dict = {
    "plex_base":       "/mnt/plex",
    "movies_dir":      "Movies",
    "tv_dir":          "TV Shows",
    "youtube_dir":     "YouTube",
    "prefer_mp4":      True,
    "embed_subs":      True,
    "embed_thumbnail": True,
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

def header() -> None:
    clr()
    console.print(Text(LOGO, style="bold cyan"), justify="center")
    console.print(
        Align.center(
            f"[dim]Terminal Video Downloader for Plex  ·  v{VERSION}  ·  yt-dlp backend[/dim]"
        )
    )
    console.print(
        Align.center(
            "[dim cyan]YouTube · Odysee · Vimeo · Twitch · TikTok · Twitter/X · Rumble · 1000+ sites[/dim cyan]"
        )
    )
    console.print()

def rule(title: str = "") -> None:
    console.print(Rule(title, style="cyan dim"))

def ok(msg: str)   -> None: console.print(f"  [bold green]✔[/bold green]  {msg}")
def err(msg: str)  -> None: console.print(f"  [bold red]✖[/bold red]  {msg}")
def info(msg: str) -> None: console.print(f"  [bold cyan]ℹ[/bold cyan]  {msg}")
def warn(msg: str) -> None: console.print(f"  [bold yellow]⚠[/bold yellow]  {msg}")

def pause() -> None:
    console.print()
    Prompt.ask("[dim]  Press Enter to continue[/dim]", default="", show_default=False)

def safe_name(s: str) -> str:
    """Strip characters illegal in Linux filenames."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', s).strip()

# ── Main menu ─────────────────────────────────────────────────────────────────
def main_menu() -> str:
    header()
    t = Table(
        show_header=False, box=box.SIMPLE, border_style="cyan dim",
        padding=(0, 3), show_edge=False,
    )
    t.add_column(style="bold yellow", no_wrap=True)
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
        title="[bold cyan]  MAIN MENU  [/bold cyan]",
        border_style="cyan",
        padding=(1, 6),
    ))
    console.print()
    return Prompt.ask("  [bold cyan]Select[/bold cyan]", default="Q").strip().upper()

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
        t.add_column(style="bold cyan", no_wrap=True, width=14)
        t.add_column(style="white")
        t.add_row("Playlist",  escape(title[:80]))
        t.add_row("Channel",   escape(str(uploader)))
        t.add_row("Videos",    str(len(entries)))
        console.print(Panel(t, title="[bold yellow]  PLAYLIST  [/bold yellow]", border_style="yellow"))
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
        t.add_column(style="bold cyan", no_wrap=True, width=14)
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
        show_header=False, box=box.SIMPLE, border_style="cyan dim",
        padding=(0, 2), show_edge=False,
    )
    t.add_column(style="bold yellow", no_wrap=True)
    t.add_column(style="white")
    for k, (label, _, _) in QUALITIES.items():
        t.add_row(f"[ {k} ]", label)
    console.print(Panel(
        t, title="[bold cyan]  SELECT QUALITY  [/bold cyan]",
        border_style="cyan", padding=(0, 4),
    ))
    console.print()
    ch = Prompt.ask("  [bold cyan]Quality[/bold cyan]", default="3").strip()
    return QUALITIES.get(ch, QUALITIES["3"])

# ── Output path builder ───────────────────────────────────────────────────────
def build_output_path(cfg: dict, info: Optional[dict], audio_only: bool) -> tuple:
    """Prompt for content type and return (output_template, content_type)."""
    base     = Path(cfg["plex_base"])
    is_pl    = (info or {}).get("_type") == "playlist"

    t = Table(
        show_header=False, box=box.SIMPLE, border_style="cyan dim",
        padding=(0, 2), show_edge=False,
    )
    t.add_column(style="bold yellow", no_wrap=True)
    t.add_column(style="white")
    for k, v in CONTENT_TYPES.items():
        t.add_row(f"[ {k} ]", v)
    console.print(Panel(
        t, title="[bold cyan]  CONTENT TYPE  [/bold cyan]",
        border_style="cyan", padding=(0, 4),
    ))
    console.print()
    ct = Prompt.ask("  [bold cyan]Type[/bold cyan]", default="3").strip()
    ctype = CONTENT_TYPES.get(ct, "YouTube / General")

    if ctype == "Movie":
        movie_title = Prompt.ask("  [bold cyan]Movie name[/bold cyan]")
        year        = Prompt.ask("  [bold cyan]Year[/bold cyan]", default="")
        s = safe_name(movie_title)
        folder = f"{s} ({year})" if year else s
        out_dir = base / cfg["movies_dir"] / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        template = str(out_dir / f"{folder}.%(ext)s")

    elif ctype == "TV Show":
        show   = Prompt.ask("  [bold cyan]Show name[/bold cyan]")
        season = Prompt.ask("  [bold cyan]Season number[/bold cyan]", default="1")
        ep_num = Prompt.ask("  [bold cyan]Starting episode number[/bold cyan]", default="1")
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
            SpinnerColumn(style="cyan"),
            TextColumn("[bold cyan]{task.description}[/]", no_wrap=True, table_column=None),
            BarColumn(bar_width=38, style="dim cyan", complete_style="bold green"),
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
        url = Prompt.ask("  [bold cyan]Enter URL[/bold cyan]").strip()
    if not url:
        warn("No URL provided.")
        pause()
        return

    console.print()
    with console.status("[cyan]Fetching video information...[/cyan]", spinner="dots"):
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
    ct.add_column(style="bold cyan", width=14)
    ct.add_column(style="white")
    ct.add_row("Quality",  ql)
    ct.add_row("Type",     ctype)
    ct.add_row("Save to",  str(Path(template).parent))
    console.print(Panel(ct, title="[bold white]  CONFIRM  [/bold white]",
                        border_style="white", padding=(0, 2)))
    console.print()

    if not Confirm.ask("  [bold cyan]Start download?[/bold cyan]", default=True):
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

    filepath = Prompt.ask("  [bold cyan]URL list file[/bold cyan]").strip()
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

    if not Confirm.ask(f"  [bold cyan]Download {len(urls)} video(s)?[/bold cyan]", default=True):
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
        box=box.SIMPLE_HEAVY, border_style="cyan dim",
        header_style="bold cyan", show_lines=False, padding=(0, 1),
    )
    t.add_column("#",       style="dim",         width=4,  justify="right")
    t.add_column("Date",    style="dim white",   width=19, no_wrap=True)
    t.add_column("Title",   style="white",       max_width=44)
    t.add_column("Type",    style="cyan",         width=13)
    t.add_column("Quality", style="yellow",       width=16)
    t.add_column("Status",  justify="center",     width=8)

    for i, h in enumerate(hist[:60], 1):
        date_str = h.get("date", "")[:19].replace("T", " ")
        status   = "[bold green]✔ OK[/bold green]" if h.get("success") else "[bold red]✖ FAIL[/bold red]"
        title    = escape(h.get("title", "Unknown")[:44])
        t.add_row(str(i), date_str, title, h.get("type","?"), h.get("quality","?"), status)

    console.print(t)
    console.print(f"  [dim]Showing {min(len(hist), 60)} of {len(hist)} entries  ·  stored in {HIST_FILE}[/dim]")
    console.print()

    if Confirm.ask("  [bold red]Clear all history?[/bold red]", default=False):
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
            show_header=False, box=box.SIMPLE, border_style="cyan dim",
            padding=(0, 2), show_edge=False,
        )
        t.add_column(style="bold yellow", no_wrap=True, width=8)
        t.add_column(style="cyan",        width=22)
        t.add_column(style="white")

        t.add_row("[ 1 ]", "Plex base path",    cfg["plex_base"])
        t.add_row("[ 2 ]", "Movies folder",     cfg["movies_dir"])
        t.add_row("[ 3 ]", "TV Shows folder",   cfg["tv_dir"])
        t.add_row("[ 4 ]", "YouTube folder",    cfg["youtube_dir"])
        t.add_row("[ 5 ]", "Prefer MP4",        "[green]Yes[/green]" if cfg["prefer_mp4"]      else "[red]No[/red]")
        t.add_row("[ 6 ]", "Embed subtitles",   "[green]Yes[/green]" if cfg["embed_subs"]       else "[red]No[/red]")
        t.add_row("[ 7 ]", "Embed thumbnail",   "[green]Yes[/green]" if cfg["embed_thumbnail"]  else "[red]No[/red]")
        t.add_row()
        t.add_row("[ B ]", "Back / Save",       "")

        console.print(Panel(t, title="[bold cyan]  CONFIGURATION  [/bold cyan]",
                            border_style="cyan", padding=(1, 2)))
        console.print()

        ch = Prompt.ask("  [bold cyan]Select[/bold cyan]", default="B").strip().upper()

        if   ch == "1": cfg["plex_base"]       = Prompt.ask("  Plex base path",    default=cfg["plex_base"])
        elif ch == "2": cfg["movies_dir"]       = Prompt.ask("  Movies folder",     default=cfg["movies_dir"])
        elif ch == "3": cfg["tv_dir"]           = Prompt.ask("  TV Shows folder",   default=cfg["tv_dir"])
        elif ch == "4": cfg["youtube_dir"]      = Prompt.ask("  YouTube folder",    default=cfg["youtube_dir"])
        elif ch == "5": cfg["prefer_mp4"]       = Confirm.ask("  Prefer MP4?",      default=cfg["prefer_mp4"])
        elif ch == "6": cfg["embed_subs"]       = Confirm.ask("  Embed subtitles?", default=cfg["embed_subs"])
        elif ch == "7": cfg["embed_thumbnail"]  = Confirm.ask("  Embed thumbnail?", default=cfg["embed_thumbnail"])
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
    with console.status("[cyan]Updating yt-dlp via pip...[/cyan]", spinner="dots"):
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
    t = Table(show_header=False, box=box.SIMPLE, border_style="cyan dim",
              padding=(0, 3), show_edge=False)
    for _ in range(cols):
        t.add_column(style="cyan", no_wrap=True)

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
    info("yt-dlp supports 1000+ sites. Full list: [cyan]yt-dlp --list-extractors[/cyan]")
    pause()

# ── Signal handler ────────────────────────────────────────────────────────────
def _sig_handler(sig, frame) -> None:
    console.print("\n\n  [bold yellow]Interrupted. Goodbye![/bold yellow]\n")
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
            console.print(Align.center("[bold cyan]Thanks for using VidGrab!  Goodbye.[/bold cyan]"))
            console.print()
            sys.exit(0)

if __name__ == "__main__":
    main()
