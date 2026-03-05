# Windows Terminal Integration

Integrate ai-launcher with Windows Terminal for one-click project access.

## Automatic Setup (WSL2)

The install script can configure this automatically:

```bash
curl -sSL https://raw.githubusercontent.com/solentlabs/ai-launcher/master/install.sh | bash
```

When prompted, choose "Yes" to configure Windows Terminal and specify your projects folder.

## Manual Setup

### 1. Find Settings

Open Windows Terminal and press `Ctrl+,` to open settings, or edit:

```
%LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json
```

### 2. Add Profile

Add this profile to the `profiles.list` array:

```json
{
    "commandline": "wsl.exe -d Ubuntu bash -lic 'ai-launcher claude ~/projects'",
    "guid": "{YOUR-UNIQUE-GUID}",
    "icon": "C:\\Users\\YOUR_USERNAME\\AppData\\Local\\wsl\\DISTRO_ID\\shortcut.ico",
    "name": "AI Launcher",
    "startingDirectory": "//wsl.localhost/Ubuntu/home/YOUR_USERNAME/projects"
}
```

**Replace:**
- `YOUR-UNIQUE-GUID` - Generate with PowerShell: `New-Guid`
- `YOUR_USERNAME` - Your Windows username
- `DISTRO_ID` - Your WSL distro ID (check in `%LOCALAPPDATA%\wsl\`)
- `~/projects` - Your actual projects path

### 3. Set as Default (Optional)

Set the `defaultProfile` to your new GUID:

```json
{
    "defaultProfile": "{YOUR-UNIQUE-GUID}",
    ...
}
```

### 4. Test

Open a new Windows Terminal window - it should launch ai-launcher!

## Multiple Project Folders

Create separate profiles for different project folders:

```json
{
    "name": "Work Projects",
    "commandline": "wsl.exe -d Ubuntu bash -lic 'ai-launcher claude ~/work'"
},
{
    "name": "Personal Projects",
    "commandline": "wsl.exe -d Ubuntu bash -lic 'ai-launcher claude ~/personal'"
}
```

## Troubleshooting

### Profile doesn't launch

1. Verify WSL is installed: `wsl --list`
2. Test command in PowerShell:
   ```powershell
   wsl.exe -d Ubuntu bash -lic 'ai-launcher claude ~/projects'
   ```

### AI provider CLI not found

Ensure your chosen AI provider CLI is installed in WSL:
```bash
which claude   # Claude Code
which gemini   # Gemini CLI
which cursor   # Cursor
which aider    # Aider
which copilot  # GitHub Copilot CLI
```

If not found, install the appropriate CLI in your WSL environment.

### Path issues

Make sure `~/.local/bin` is in your PATH:
```bash
echo $PATH | grep .local/bin
```

If missing, add to `~/.bashrc`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```
