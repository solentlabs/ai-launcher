# Troubleshooting

## Installation Issues

### "Fatal error in launcher: Unable to create process" (Windows)

The Windows pip launcher script has a broken path reference.

**Fix:** Use `py -m pip` instead of `pip`:

```powershell
py -m pip install ai-launcher
```

### AI provider CLI not found

Your chosen AI provider CLI is not installed or not in PATH.

**Check:**

```bash
# Linux / macOS / WSL
which claude   # Claude Code
which gemini   # Gemini CLI
which cursor   # Cursor
which aider    # Aider
which copilot  # GitHub Copilot CLI
```

```powershell
# Windows (PowerShell)
Get-Command claude   # Claude Code
Get-Command gemini   # Gemini CLI
Get-Command cursor   # Cursor
Get-Command aider    # Aider
Get-Command copilot  # GitHub Copilot CLI
```

**Fix:** Install the appropriate CLI for your provider and ensure it's in your PATH.

### "fzf not found"

fzf is not installed.

**Fix:**

```bash
# Ubuntu/Debian/WSL
sudo apt install fzf

# macOS
brew install fzf
```

```powershell
# Windows (pick one)
winget install junegunn.fzf
scoop install fzf
choco install fzf
```

### "externally-managed-environment" error

Python PEP 668 prevents system-wide package installation.

**Fix:** Use pipx:

```bash
sudo apt install pipx
pipx install ai-launcher
```

### `ai-launcher` command not found after install (Windows)

The Scripts directory may not be in your PATH.

**Fix:** Either add it to PATH or use the module directly:

```powershell
py -m ai_launcher --version
py -m ai_launcher C:\Users\you\projects
```

To find where pip installed it:

```powershell
py -m pip show ai-launcher
```

## Runtime Issues

### No projects found

**Causes:**
1. No scan paths provided on the command line
2. Paths don't contain git repositories
3. Permissions issue

**Fix:**

```bash
# Verify the path you're passing contains git repos
ls ~/projects
find ~/projects -name .git -type d
```

On Windows:

```powershell
Get-ChildItem -Path C:\Users\you\projects -Filter .git -Recurse -Directory
```

### Preview shows errors

**Fix:** Upgrade to latest version:

```bash
pipx upgrade ai-launcher
```

### Database errors

**Symptom:** "Database corruption detected"

**Fix:** The database auto-recovers. Check for backup:

```bash
ls ~/.local/share/ai-launcher/*.backup.*
```

To restore manually:

```bash
cd ~/.local/share/ai-launcher
cp projects.db.backup.TIMESTAMP projects.db
```

### Permission denied during scan

**Symptom:** Warnings about unreadable directories.

**Fix:** These are automatically skipped. Directories like `node_modules`, `.cache`, and `venv` are pruned by default. No configuration needed.

## Terminal Title Issues

AI Launcher automatically sets the terminal window title (e.g., `my-app → Claude Code`) when launching a project. This works on most modern terminals including xterm, iTerm2, GNOME Terminal, Windows Terminal, tmux, and VS Code. Basic CMD.exe on Windows is not supported.

### Terminal title not changing?

1. **Check if your terminal supports title setting:**
   Most modern terminals do, but some minimal terminals don't.

2. **Try setting TERM environment variable:**
   ```bash
   export TERM=xterm-256color
   ai-launcher claude ~/projects
   ```

### Terminal title persists after closing AI tool?

This is normal. Most terminals keep the last set title until the window is closed or another program sets a new title.

To manually clear the title:
```bash
echo -ne "\033]0;\007"
```

## Windows Terminal Issues

### Profile doesn't launch

1. **Verify WSL:**
   ```powershell
   wsl --list
   ```

2. **Test command:**
   ```powershell
   wsl.exe -d Ubuntu bash -lic 'ai-launcher --version'
   ```

3. **Check terminal settings path:**
   ```
   %LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json
   ```

### PATH not found in WSL

Add to `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then restart terminal or:

```bash
source ~/.bashrc
```

## Performance Issues

### Slow project scanning

**Cause:** Scanning too many directories or too deep.

**Fix:** Pass a more specific path to reduce scan scope:

```bash
# Instead of scanning everything
ai-launcher claude ~/projects

# Scan a narrower subtree
ai-launcher claude ~/projects/solentlabs
```

### Slow startup

**Cause:** Large database from many scanned projects.

**Fix:** Check database size:

```bash
ls -lh ~/.local/share/ai-launcher/projects.db
```

## Getting Help

If issues persist:

1. **Check GitHub Issues:** https://github.com/solentlabs/ai-launcher/issues
2. **Enable verbose logging:**
   ```bash
   ai-launcher claude --verbose ~/projects
   ```
3. **Report bug with:**
   - OS and version
   - Python version (`python3 --version` or `py --version`)
   - Error messages
   - Steps to reproduce
