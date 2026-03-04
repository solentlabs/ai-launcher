# Adding New AI Providers

This guide shows how to add support for new AI CLI tools to AI Launcher.

## Quick Reference: Popular AI Tools

| Tool | CLI Command | Context Files | Status |
|------|-------------|---------------|--------|
| **Claude Code** | `claude` | `CLAUDE.md`, `.clauderc` | ✅ Built-in |
| **Gemini CLI** | `gemini` | `GEMINI.md`, `.geminirc` | ✅ Built-in |
| **Aider** | `aider` | `.aider.conf.yml`, `AIDER.md` | 📝 Template below |
| **Cursor** | `cursor` | `.cursorrules`, `CURSOR.md` | 📝 Template below |
| **GitHub Copilot** | `gh copilot` | None (uses git context) | 📝 Template below |
| **Continue** | `continue` | `.continuerc.json` | 📝 Template below |
| **Windsurf** | `windsurf` | `.windsurfrules` | 📝 Template below |
| **Cody** | `cody` | `.cody/config.json` | 📝 Template below |

## Architecture Overview

```
providers/
├── __init__.py         # Package exports
├── base.py             # AIProvider ABC
├── registry.py         # Provider registry
├── claude.py           # ClaudeProvider ✅
├── gemini.py           # GeminiProvider ✅
├── aider.py            # AiderProvider (add this)
├── cursor.py           # CursorProvider (add this)
└── copilot.py          # CopilotProvider (add this)
```

## Step-by-Step: Adding a Provider

### 1. Create Provider File

Create `src/ai_launcher/providers/your_tool.py`:

```python
"""Your Tool provider implementation."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ai_launcher.providers.base import AIProvider, ProviderMetadata

if TYPE_CHECKING:
    from ai_launcher.core.models import CleanupConfig


class YourToolProvider(AIProvider):
    """Your Tool provider implementation."""

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="your-tool",              # Internal ID (kebab-case)
            display_name="Your Tool",      # Display name
            command="yourtool",             # CLI command
            description="Your tool description",
            config_files=["YOURTOOL.md"],   # Context files
            requires_installation=True,
        )

    def is_installed(self) -> bool:
        """Check if tool CLI is installed."""
        return shutil.which("yourtool") is not None

    def launch(self, project_path: Path) -> None:
        """Launch tool in project directory."""
        os.chdir(project_path)
        try:
            subprocess.run(["yourtool"], check=True)
        except FileNotFoundError:
            print(f"Error: '{self.metadata.command}' command not found.")
            print(f"Install: {self.metadata.description}")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error launching {self.metadata.display_name}: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            sys.exit(0)

    def cleanup_environment(
        self, verbose: bool = False, cleanup_config: Optional["CleanupConfig"] = None
    ) -> None:
        """Clean tool-specific cache/logs."""
        # Only clean if enabled
        if not cleanup_config or not cleanup_config.enabled:
            return

        if not cleanup_config.clean_provider_files:
            return

        # Clean tool-specific cache
        cache_dir = Path.home() / ".yourtool" / "cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
            if verbose:
                print(f"  → Cleaned {self.metadata.display_name} cache")
```

### 2. Register Provider

Edit `src/ai_launcher/providers/registry.py`:

```python
from ai_launcher.providers.claude import ClaudeProvider
from ai_launcher.providers.gemini import GeminiProvider
from ai_launcher.providers.yourtool import YourToolProvider  # Add import

class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, AIProvider] = {}

        self.register(ClaudeProvider())
        self.register(GeminiProvider())
        self.register(YourToolProvider())  # Add registration
```

### 3. Test Provider

```bash
# Check if recognized
ai-launcher --providers

# Launch with your tool
ai-launcher your-tool ~/projects

# Or set as default
# ~/.config/ai-launcher/config.toml
[provider]
default = "your-tool"
```

## Ready-to-Use Providers

### Aider Provider

```python
"""Aider AI pair programming provider."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ai_launcher.providers.base import AIProvider, ProviderMetadata

if TYPE_CHECKING:
    from ai_launcher.core.models import CleanupConfig


class AiderProvider(AIProvider):
    """Aider AI pair programming tool provider.

    Aider is a terminal-based AI pair programming tool that works with
    various LLMs (GPT-4, Claude, etc.) via API.

    Install: pip install aider-chat
    Docs: https://aider.chat/
    """

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="aider",
            display_name="Aider",
            command="aider",
            description="AI pair programming in the terminal",
            config_files=[".aider.conf.yml", "AIDER.md"],
            requires_installation=True,
        )

    def is_installed(self) -> bool:
        return shutil.which("aider") is not None

    def launch(self, project_path: Path) -> None:
        os.chdir(project_path)

        # Check for config file
        config_file = project_path / ".aider.conf.yml"
        cmd = ["aider"]
        if config_file.exists():
            cmd.extend(["--config", str(config_file)])

        try:
            subprocess.run(cmd, check=True)
        except FileNotFoundError:
            print("Error: 'aider' command not found.")
            print("Install: pip install aider-chat")
            print("Docs: https://aider.chat/")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error launching Aider: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            sys.exit(0)

    def cleanup_environment(
        self, verbose: bool = False, cleanup_config: Optional["CleanupConfig"] = None
    ) -> None:
        """Clean Aider cache."""
        if not cleanup_config or not cleanup_config.enabled:
            return

        if not cleanup_config.clean_provider_files:
            return

        # Aider stores cache in ~/.aider
        aider_dir = Path.home() / ".aider"
        if aider_dir.exists():
            cache_dir = aider_dir / "cache"
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
                if verbose:
                    print("  → Cleaned Aider cache")
```

### Cursor Provider

```python
"""Cursor IDE provider."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ai_launcher.providers.base import AIProvider, ProviderMetadata

if TYPE_CHECKING:
    from ai_launcher.core.models import CleanupConfig


class CursorProvider(AIProvider):
    """Cursor AI-first code editor provider.

    Cursor is a fork of VS Code with built-in AI features.

    Install: https://cursor.sh/
    """

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="cursor",
            display_name="Cursor",
            command="cursor",
            description="AI-first code editor",
            config_files=[".cursorrules", "CURSOR.md"],
            requires_installation=True,
        )

    def is_installed(self) -> bool:
        return shutil.which("cursor") is not None

    def launch(self, project_path: Path) -> None:
        os.chdir(project_path)

        try:
            # Cursor needs the directory path
            subprocess.run(["cursor", "."], check=True)
        except FileNotFoundError:
            print("Error: 'cursor' command not found.")
            print("Install: https://cursor.sh/")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error launching Cursor: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            sys.exit(0)

    def cleanup_environment(
        self, verbose: bool = False, cleanup_config: Optional["CleanupConfig"] = None
    ) -> None:
        """Clean Cursor cache."""
        if not cleanup_config or not cleanup_config.enabled:
            return

        if not cleanup_config.clean_provider_files:
            return

        # Cursor stores data in various locations
        cursor_dirs = [
            Path.home() / ".cursor",
            Path.home() / ".config" / "Cursor",
            Path.home() / "Library" / "Application Support" / "Cursor",  # macOS
        ]

        for cursor_dir in cursor_dirs:
            if cursor_dir.exists():
                cache_dir = cursor_dir / "Cache"
                if cache_dir.exists():
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    if verbose:
                        print("  → Cleaned Cursor cache")
                    break
```

### GitHub Copilot CLI Provider

```python
"""GitHub Copilot CLI provider."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ai_launcher.providers.base import AIProvider, ProviderMetadata

if TYPE_CHECKING:
    from ai_launcher.core.models import CleanupConfig


class CopilotProvider(AIProvider):
    """GitHub Copilot CLI provider.

    GitHub's AI assistant for the command line.

    Install: gh extension install github/gh-copilot
    Docs: https://docs.github.com/en/copilot/github-copilot-in-the-cli
    """

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="copilot",
            display_name="GitHub Copilot CLI",
            command="gh",  # Uses gh CLI
            description="GitHub's AI assistant for the CLI",
            config_files=[],  # Uses git context automatically
            requires_installation=True,
        )

    def is_installed(self) -> bool:
        """Check if gh CLI and copilot extension are installed."""
        if not shutil.which("gh"):
            return False

        # Check if copilot extension is installed
        try:
            result = subprocess.run(
                ["gh", "extension", "list"],
                capture_output=True,
                text=True,
                check=False,
            )
            return "gh-copilot" in result.stdout
        except Exception:
            return False

    def launch(self, project_path: Path) -> None:
        os.chdir(project_path)

        try:
            # Launch copilot chat
            subprocess.run(["gh", "copilot", "chat"], check=True)
        except FileNotFoundError:
            print("Error: 'gh' command not found.")
            print("Install: https://cli.github.com/")
            print("Then: gh extension install github/gh-copilot")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error launching GitHub Copilot: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            sys.exit(0)

    def cleanup_environment(
        self, verbose: bool = False, cleanup_config: Optional["CleanupConfig"] = None
    ) -> None:
        """Clean Copilot cache."""
        if not cleanup_config or not cleanup_config.enabled:
            return

        if not cleanup_config.clean_provider_files:
            return

        # GitHub CLI cache
        gh_cache = Path.home() / ".config" / "gh" / "copilot"
        if gh_cache.exists():
            cache_dir = gh_cache / "cache"
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
                if verbose:
                    print("  → Cleaned GitHub Copilot cache")
```

## Provider Variations

### Tool with Default Arguments

Some tools need specific flags:

```python
def launch(self, project_path: Path) -> None:
    os.chdir(project_path)

    # Always launch with specific model
    cmd = ["aider", "--model", "gpt-4", "--auto-commits"]
    subprocess.run(cmd, check=True)
```

### Tool with API Key Check

Some tools require API keys:

```python
def is_installed(self) -> bool:
    """Check both CLI and API key."""
    if not shutil.which("aider"):
        return False

    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    return api_key is not None
```

### Tool with Multiple Commands

Some tools are subcommands:

```python
@property
def metadata(self) -> ProviderMetadata:
    return ProviderMetadata(
        name="copilot",
        command="gh copilot",  # Space-separated
        # ...
    )

def launch(self, project_path: Path) -> None:
    subprocess.run(["gh", "copilot", "chat"], check=True)
```

### Tool Without Cleanup

Some tools don't need cleanup:

```python
def cleanup_environment(self, verbose: bool, cleanup_config) -> None:
    """No cleanup needed for this tool."""
    pass
```

## Testing Your Provider

```bash
# 1. Check if detected
ai-launcher --providers

Expected output:
  ✓ Your Tool (yourtool)
    Status: Installed

# 2. Launch directly
ai-launcher your-tool ~/projects

# 3. Set as default
echo '[provider]
default = "your-tool"' >> ~/.config/ai-launcher/config.toml

# 4. Test per-project override
# Edit ~/.config/ai-launcher/config.toml
```

## Common Patterns

### Pattern 1: Python Package

```python
def is_installed(self) -> bool:
    try:
        import your_package
        return True
    except ImportError:
        return False
```

### Pattern 2: Node Package

```python
def is_installed(self) -> bool:
    # Check if installed via npm
    try:
        result = subprocess.run(
            ["npm", "list", "-g", "your-package"],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False
```

### Pattern 3: IDE/Editor

```python
def launch(self, project_path: Path) -> None:
    # Don't cd, pass path as argument
    subprocess.run(["your-ide", str(project_path)], check=True)
```

## Contribution Guidelines

If adding a provider to the official repo:

1. **Provider file** - Follow naming: `src/ai_launcher/providers/toolname.py`
2. **Docstrings** - Include tool description and install instructions
3. **Type hints** - Full type annotations required
4. **Error handling** - Helpful error messages with install links
5. **Register** - Add to `registry.py`
6. **Test** - Verify `--providers` shows it, launching works
7. **Document** - Add to this guide's Quick Reference table

## Future Enhancements

Planned improvements to provider system:

- **Auto-discovery** - Scan `providers/` directory automatically
- **Plugin system** - Load providers from `~/.local/share/ai-launcher/plugins/`
- **Capability flags** - Declare what features each provider supports
- **Launch options** - Pass provider-specific CLI arguments

## Resources

- **Provider ABC**: `src/ai_launcher/providers/base.py`
- **Registry**: `src/ai_launcher/providers/registry.py`
- **Examples**: `src/ai_launcher/providers/claude.py`
- **Tests**: `tests/test_providers.py`
