# AI Launcher

Universal AI CLI launcher with local context management. Launch any AI coding assistant from a single entry point with persistent context across sessions.

[![PyPI version](https://img.shields.io/pypi/v/ai-launcher)](https://pypi.org/project/ai-launcher/)
[![CI](https://github.com/solentlabs/ai-launcher/actions/workflows/ci.yml/badge.svg)](https://github.com/solentlabs/ai-launcher/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/solentlabs/ai-launcher/graph/badge.svg)](https://codecov.io/gh/solentlabs/ai-launcher)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Local-First Design** - All context and data stays on your machine. No cloud dependencies.

## What Is This?

A terminal-first launcher that:
- 🎯 **Single Entry Point** - One command to access all your AI coding tools
- 🧠 **Context Management** - Maintains persistent context across sessions
- 🔒 **Local-Only** - Everything stays on your machine
- 🔍 **Project Switching** - Fuzzy search across all your projects
- 🤖 **Multi-Tool Support** - Works with Claude Code, Gemini CLI, and more
- 👁️ **Context Transparency** - See exactly what files AI tools access
- 🖥️ **Cross-Platform** - Native support for Linux, macOS, WSL, and Windows

## Install

<details open>
<summary><strong>Linux / macOS / WSL</strong></summary>

```bash
# Install fzf (required)
sudo apt install fzf    # Ubuntu/Debian/WSL
brew install fzf         # macOS

# Install ai-launcher
pipx install ai-launcher
```

</details>

<details>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
# Install fzf (required - pick one)
winget install junegunn.fzf
scoop install fzf
choco install fzf

# Install ai-launcher
pipx install ai-launcher

# Or with pip (use py -m to avoid launcher issues)
py -m pip install ai-launcher
```

</details>

<details>
<summary><strong>From source</strong></summary>

```bash
git clone https://github.com/solentlabs/ai-launcher.git
cd ai-launcher
pip install -e .
```

</details>

## Use

<details open>
<summary><strong>Linux / macOS / WSL</strong></summary>

```bash
ai-launcher ~/projects
```

</details>

<details>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
ai-launcher C:\Users\you\projects

# If ai-launcher is not in PATH
py -m ai_launcher C:\Users\you\projects
```

</details>

**See what's available:**
```bash
ai-launcher --discover ~/projects
ai-launcher --context
```

Select a project, and your AI tool opens with full context.

## Features

### Project Management
- 🔍 **Fuzzy search** - Type to filter projects instantly
- 📁 **Tree navigation** - See your project structure at a glance
- 📋 **Preview pane** - Git status, context files, directory contents
- ⚡ **Last opened** - Cursor starts on your most recent project
- ➕ **Manual projects** - Add non-git directories
- 🔗 **Symlink support** - Works with linked directories

### Multi-Provider Support
- 🤖 **Provider abstraction** - Switch between Claude Code, Gemini, and more
- 🔧 **Per-project configuration** - Different AI tools for different projects
- 📊 **Discovery mode** - See what providers are installed
- 👁️ **Context visualization** - View what files AI tools access
- 🧠 **Context awareness** - Detects CLAUDE.md, GEMINI.md, and other context files

### Terminal Window Title
- 📺 **Auto title setting** - Terminal shows "project → provider" for easy window identification
- 🎨 **Customizable format** - Configure your preferred title style
- 🪟 **Multi-window workflow** - Instantly identify which terminal has which project
- 🖥️ **Broad compatibility** - Works with xterm, iTerm2, GNOME Terminal, Windows Terminal, tmux, and more

## Requirements

- Python 3.8+
- [fzf](https://github.com/junegunn/fzf) (fuzzy search — see install steps above)
- An AI CLI tool (Claude Code, Gemini CLI, Cursor, Aider, or GitHub Copilot CLI)

## Configuration

First run creates `~/.config/ai-launcher/config.toml`:

```toml
[scan]
paths = ["~/projects", "~/work"]    # Linux/macOS/WSL
# paths = ["C:/Users/you/projects"] # Windows
max_depth = 5

[provider]
default = "claude-code"

# Per-project overrides (optional)
[provider.per_project]
"/home/user/gemini-project" = "gemini"         # Linux/macOS/WSL
# "C:/Users/you/gemini-project" = "gemini"     # Windows
```

### Available Providers

- **claude-code** - Anthropic's Claude Code
- **gemini** - Google's Gemini CLI
- **cursor** - Cursor IDE
- **aider** - Aider pair programmer
- **copilot** - GitHub Copilot CLI

## Why Local-Only?

Your code and context should stay on your machine. AI Launcher:
- Never sends data to external services
- Works offline
- Respects your privacy
- Gives you full control

## Documentation

- [Installation Guide](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Windows Terminal Setup](docs/windows-terminal.md)
- [Troubleshooting](docs/troubleshooting.md)

## License

MIT - see [LICENSE](LICENSE)

---

**Made by [Solent Labs™](https://github.com/solentlabs)** - Building tools for developers who value privacy and local-first software.
