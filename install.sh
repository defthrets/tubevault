#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════╗
# ║          TubeVault Installer  ·  Debian 13 / Ubuntu           ║
# ╚══════════════════════════════════════════════════════════════╝

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
CYAN='\033[0;36m'; BOLD='\033[1m'; GREEN='\033[0;32m'
YELLOW='\033[1;33m'; RED='\033[0;31m'; RESET='\033[0m'

ok()   { echo -e "  ${GREEN}✔${RESET}  $1"; }
info() { echo -e "  ${CYAN}ℹ${RESET}  $1"; }
warn() { echo -e "  ${YELLOW}⚠${RESET}  $1"; }
err()  { echo -e "  ${RED}✖${RESET}  $1"; exit 1; }
sep()  { echo -e "  ${CYAN}────────────────────────────────────────${RESET}"; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}"
cat << 'BANNER'
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
BANNER
echo -e "${RESET}"
echo -e "  ${BOLD}Terminal Video Downloader for Plex  ·  Debian 13 Installer${RESET}"
sep
echo ""

# ── Root check ────────────────────────────────────────────────────────────────
if [[ "$EUID" -ne 0 ]]; then
    warn "Needs root. Re-running with sudo..."
    exec sudo bash "$0" "$@"
fi

INSTALL_DIR="/opt/tubevault"
BIN_LINK="/usr/local/bin/tubevault"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── System packages ───────────────────────────────────────────────────────────
info "Updating package list..."
apt-get update -qq

info "Installing system dependencies..."
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    atomicparsley \
    curl

ok "System packages installed."
echo ""

# ── Python virtual environment ────────────────────────────────────────────────
info "Creating install directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

info "Creating Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
ok "Virtual environment ready."

info "Installing Python packages (rich, yt-dlp)..."
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet rich yt-dlp
ok "Python packages installed."
echo ""

# ── Install script ────────────────────────────────────────────────────────────
info "Copying tubevault.py to $INSTALL_DIR..."
cp "$SCRIPT_DIR/tubevault.py" "$INSTALL_DIR/tubevault.py"
chmod 644 "$INSTALL_DIR/tubevault.py"

# Create wrapper launcher
cat > "$INSTALL_DIR/tubevault" << 'WRAPPER'
#!/usr/bin/env bash
exec /opt/tubevault/venv/bin/python /opt/tubevault/tubevault.py "$@"
WRAPPER
chmod +x "$INSTALL_DIR/tubevault"

# Global symlink
ln -sf "$INSTALL_DIR/tubevault" "$BIN_LINK"
ok "Installed: $BIN_LINK"
echo ""

# ── Plex media directory setup ────────────────────────────────────────────────
sep
echo ""
echo -e "  ${BOLD}Plex Media Directory Setup${RESET}"
echo ""
info "Default path is /srv/media — change this to match your Plex library."
echo ""
read -rp "  Plex media base path [/srv/media]: " PLEX_PATH
PLEX_PATH="${PLEX_PATH:-/srv/media}"

for d in "Movies" "TV Shows" "YouTube"; do
    mkdir -p "$PLEX_PATH/$d"
    ok "Created: $PLEX_PATH/$d"
done
echo ""

# ── Write default config ──────────────────────────────────────────────────────
# Write config for root and for the actual user who ran sudo
write_config() {
    local CONFIG_DIR="$1/.config/tubevault"
    mkdir -p "$CONFIG_DIR"
    cat > "$CONFIG_DIR/config.json" << CONFIG
{
  "plex_base": "$PLEX_PATH",
  "movies_dir": "Movies",
  "tv_dir": "TV Shows",
  "youtube_dir": "YouTube",
  "prefer_mp4": true,
  "embed_subs": true,
  "embed_thumbnail": true
}
CONFIG
    ok "Config written: $CONFIG_DIR/config.json"
}

write_config "$HOME"

# Also write for the original user if sudo was used
if [[ -n "${SUDO_USER:-}" ]]; then
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    if [[ -n "$REAL_HOME" && "$REAL_HOME" != "$HOME" ]]; then
        write_config "$REAL_HOME"
        chown -R "$SUDO_USER:$SUDO_USER" "$REAL_HOME/.config/tubevault"
    fi
fi

echo ""
sep
echo ""
echo -e "  ${GREEN}${BOLD}Installation complete!${RESET}"
echo ""
echo -e "  Run:   ${CYAN}${BOLD}tubevault${RESET}"
echo -e "  URL:   ${CYAN}${BOLD}tubevault 'https://youtube.com/watch?v=...'${RESET}"
echo ""
echo -e "  ${BOLD}yt-dlp version:${RESET}"
"$INSTALL_DIR/venv/bin/python" -c "import yt_dlp; print('  ' + yt_dlp.version.__version__)"
echo ""
sep
echo ""






