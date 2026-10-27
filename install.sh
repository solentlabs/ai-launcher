#!/usr/bin/env bash
set -e

# Questions are read from the keyboard, not stdin: this script is documented as
# `curl ... | bash`, where stdin is the script itself and a plain `read` would
# swallow its next lines. INSTALL_TTY and INSTALL_PROC_VERSION exist so tests can
# stand in for /dev/tty and /proc/version.
TTY_SOURCE="${INSTALL_TTY:-/dev/tty}"
HAVE_TTY=0
if exec 3< "$TTY_SOURCE" 2> /dev/null; then
    HAVE_TTY=1
fi

# ask "question" -> true only if the user typed y/Y. No keyboard means no.
ask() {
    local reply=""
    if [ "$HAVE_TTY" = 1 ]; then
        printf '%s' "$1" > /dev/tty 2> /dev/null || printf '%s' "$1"
        read -r -u 3 reply || true
    fi
    [[ $reply =~ ^[Yy] ]]
}

# ask_line "question" "default" -> sets REPLY_LINE (the default with no keyboard)
ask_line() {
    REPLY_LINE=""
    if [ "$HAVE_TTY" = 1 ]; then
        printf '%s' "$1" > /dev/tty 2> /dev/null || printf '%s' "$1"
        read -r -u 3 REPLY_LINE || true
    fi
    REPLY_LINE="${REPLY_LINE:-$2}"
}

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Installing ai-launcher...${NC}"

# Check if pipx is installed
if ! command -v pipx &> /dev/null; then
    echo "Installing pipx..."
    if command -v apt &> /dev/null; then
        sudo apt update && sudo apt install -y pipx
    elif command -v brew &> /dev/null; then
        brew install pipx
    elif command -v choco &> /dev/null; then
        choco install pipx
    else
        echo "Error: Could not detect package manager. Please install pipx manually."
        exit 1
    fi
fi

# Install ai-launcher
echo "Installing ai-launcher..."
pipx install ai-launcher

# Ensure PATH is configured
echo "Configuring PATH..."
pipx ensurepath

# Check if fzf is installed
if ! command -v fzf &> /dev/null; then
    echo ""
    echo "Note: fzf is required for ai-launcher."
    if command -v apt &> /dev/null; then
        if ask "Install fzf now? (y/n) "; then
            sudo apt install -y fzf
        fi
    else
        echo "Please install fzf manually:"
        echo "  - macOS: brew install fzf"
        echo "  - Windows: choco install fzf"
    fi
fi

# Configure Windows Terminal profile (WSL2 only). See docs/windows-terminal.md for
# exactly what this changes. Values reach Python through the environment, never by
# being spliced into its source: what you type is data.
if grep -qi microsoft "${INSTALL_PROC_VERSION:-/proc/version}" 2> /dev/null; then
    echo ""
    if ask "Configure Windows Terminal profile? (y/n) "; then
        ask_line "Enter default projects folder (default: ~/projects): " "$HOME/projects"
        PROJECTS_PATH="${REPLY_LINE/#\~/$HOME}"

        WIN_USER=$(cmd.exe /c "echo %USERNAME%" 2> /dev/null | tr -d '\r' || true)
        WT_REL="AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json"
        WT_SETTINGS="$HOME/$WT_REL"
        if [ ! -f "$WT_SETTINGS" ] && [ -n "$WIN_USER" ]; then
            WT_SETTINGS="/mnt/c/Users/${WIN_USER}/$WT_REL"
        fi

        if [ ! -f "$WT_SETTINGS" ]; then
            echo "Windows Terminal settings not found, skipping profile configuration"
        elif [[ "$PROJECTS_PATH" == *\"* ]]; then
            echo "A double quote in the projects folder cannot be put in the profile; skipping."
            echo "Add the profile by hand: docs/windows-terminal.md"
        else
            MAKE_DEFAULT=0
            if ask "Make it your default Windows Terminal profile? (y/n) "; then
                MAKE_DEFAULT=1
            fi
            WT_SETTINGS="$WT_SETTINGS" PROJECTS_PATH="$PROJECTS_PATH" WIN_USER="$WIN_USER" \
                NEW_GUID="$(uuidgen | tr '[:upper:]' '[:lower:]')" MAKE_DEFAULT="$MAKE_DEFAULT" \
                python3 - << 'PY' || true
import json
import os
import shlex
import shutil
import tempfile

path = os.environ["WT_SETTINGS"]
projects = os.environ["PROJECTS_PATH"]
win_user = os.environ.get("WIN_USER", "")

try:
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    profiles = config["profiles"]["list"]
except (OSError, ValueError, KeyError, TypeError) as error:
    # Windows Terminal allows comments in this file, which plain JSON does not.
    print(f"Windows Terminal settings could not be read as JSON ({error}); left unchanged.")
    print("Add the profile by hand: docs/windows-terminal.md")
    raise SystemExit(0)

if any(p.get("name") in ("AI Launcher", "Claude Code") for p in profiles):
    print("An AI Launcher profile already exists in Windows Terminal")
    raise SystemExit(0)

guid = "{" + os.environ["NEW_GUID"] + "}"
profile = {
    "commandline": 'wsl.exe -d Ubuntu bash -lic "ai-launcher claude '
    + shlex.quote(projects)
    + '"',
    "guid": guid,
    "name": "AI Launcher",
    "startingDirectory": "//wsl.localhost/Ubuntu" + projects,
}
if win_user:
    profile["icon"] = (
        "C:\\Users\\" + win_user + "\\AppData\\Local\\wsl\\"
        "{a0446c4a-5b36-463f-b64f-09d8c4c55c8c}\\shortcut.ico"
    )
profiles.insert(0, profile)
if os.environ.get("MAKE_DEFAULT") == "1":
    config["defaultProfile"] = guid

# Back up, then replace through a temporary file: a failure cannot leave half a file.
shutil.copy2(path, path + ".ai-launcher.bak")
handle, temp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
with os.fdopen(handle, "w", encoding="utf-8") as out:
    json.dump(config, out, indent=4)
os.replace(temp, path)
print("✓ Windows Terminal profile added (backup: settings.json.ai-launcher.bak)")
PY
        fi
    fi
fi

echo ""
echo -e "${GREEN}✓ Installation complete!${NC}"
echo ""
echo "Run: ai-launcher --version"
echo "     ai-launcher claude ~/projects"
echo ""
echo "Note: You may need to restart your terminal for PATH changes to take effect."
