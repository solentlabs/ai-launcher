# Installation Guide

## Quick Install

### Linux / macOS / WSL

```bash
# Install dependencies
sudo apt install pipx fzf    # Ubuntu/Debian/WSL
brew install pipx fzf         # macOS

# Install ai-launcher
pipx install ai-launcher
pipx ensurepath
```

### Windows (PowerShell)

```powershell
# Install fzf (pick one)
winget install junegunn.fzf
scoop install fzf
choco install fzf

# Install ai-launcher
pipx install ai-launcher

# If pipx is not available, use py -m pip
py -m pip install ai-launcher
```

> **Note:** On Windows, use `py -m pip` instead of `pip` directly if you get
> "Fatal error in launcher: Unable to create process". This is a known Windows
> pip launcher issue, not specific to ai-launcher.

## Verify Installation

```bash
ai-launcher --version
```

On Windows, if `ai-launcher` is not found in PATH:

```powershell
py -m ai_launcher --version
```

## Usage

### Linux / macOS / WSL

```bash
ai-launcher ~/projects
```

### Windows (PowerShell)

```powershell
ai-launcher C:\Users\you\projects
```

Or if the entry point isn't in PATH:

```powershell
py -m ai_launcher C:\Users\you\projects
```

## From Source

```bash
git clone https://github.com/solentlabs/ai-launcher.git
cd ai-launcher
pip install -e ".[dev]"
```

## Dependencies

| Dependency | Required | Install |
|---|---|---|
| Python 3.8+ | Yes | [python.org](https://www.python.org/downloads/) |
| fzf | Yes | `apt install fzf` / `brew install fzf` / `winget install junegunn.fzf` |
| An AI CLI tool | Yes | Claude Code, Gemini CLI, Cursor, Aider, or GitHub Copilot CLI |
| Git | No | For project discovery (recommended) |

## Troubleshooting

See [Troubleshooting Guide](troubleshooting.md) for common issues.
