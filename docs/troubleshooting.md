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
1. No scan paths configured
2. Paths don't contain git repositories
3. Permissions issue

**Fix:**

```bash
# Check configuration
cat ~/.config/ai-launcher/config.toml

# Verify paths exist and contain git repos
ls ~/projects
find ~/projects -name .git -type d
```

On Windows:

```powershell
Get-Content ~\.config\ai-launcher\config.toml
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

**Fix:** These are automatically skipped. To reduce warnings, add to `prune_dirs` in config:

```toml
[scan]
prune_dirs = [
    "node_modules",
    ".cache",
    "restricted-dir",
]
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

**Cause:** Scanning too many files or too deep.

**Fix:** Reduce `max_depth` or add more `prune_dirs`:

```toml
[scan]
max_depth = 3
prune_dirs = [
    "node_modules",
    ".cache",
    "venv",
    "build",
    "dist",
    ".venv",
]
```

### Slow startup

**Cause:** Too many manual projects or large history.

**Fix:** Clean up:

```bash
# Check database size
ls -lh ~/.local/share/ai-launcher/projects.db

# Reduce history in config
[history]
max_entries = 10
```

## Getting Help

If issues persist:

1. **Check GitHub Issues:** https://github.com/solentlabs/ai-launcher/issues
2. **Enable verbose logging:**
   ```bash
   ai-launcher --verbose ~/projects
   ```
3. **Report bug with:**
   - OS and version
   - Python version (`python3 --version` or `py --version`)
   - Error messages
   - Steps to reproduce
