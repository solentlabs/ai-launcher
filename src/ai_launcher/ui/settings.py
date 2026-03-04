"""Settings management UI for ai-launcher.

This module provides an interactive settings menu using fzf that allows users
to configure AI Launcher behavior, particularly cleanup operations. Settings
are persisted to the configuration file and can be toggled with arrow keys.

Author: Solent Labs™
Created: 2026-02-10
"""

import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import List, Optional

from ai_launcher.core.config import ConfigManager
from ai_launcher.core.models import ConfigData


def show_settings_menu(
    config_manager: ConfigManager,
    scan_paths: Optional[List[Path]] = None,
) -> bool:
    """Show interactive settings menu using fzf.

    Args:
        config_manager: Config manager for loading/saving settings
        scan_paths: Optional scan paths for global files management

    Returns:
        True if settings were changed, False otherwise
    """
    config = config_manager.load()
    changes_made = False

    while True:
        # Build settings menu items
        choices = _build_settings_choices(config)

        # Build mapping from display text to full metadata
        display_to_meta = {}
        for choice in choices:
            if "\t\t" in choice:
                meta, display = choice.split("\t\t", 1)
                display_to_meta[display] = meta

        # Build header
        header = """╭─────────────────────────────────────────╮
│               Settings                  │
│          by Solent Labs™                │
╰─────────────────────────────────────────╯

Configure AI Launcher behavior
SPACE to toggle • ENTER to open • ESC to go back
"""

        # Build preview command using helper script
        helper_script = Path(__file__).parent / "_settings_preview.py"
        preview_cmd = f"{sys.executable} {helper_script} {{}}"

        # Run fzf
        try:
            fzf_cmd = [
                "fzf",
                "--disabled",  # Disable search/filter
                "--height=100%",
                "--layout=reverse",
                "--border=rounded",
                "--border-label= Settings ",
                "--delimiter=\\t\\t",
                "--with-nth=2..",  # Show only the display part
                "--preview-window=right:60%:wrap:border-left",
                f"--preview={preview_cmd}",
                f"--header={header}",
                "--header-first",
                "--ansi",
                "--expect=space",  # Capture space key for toggle
            ]

            input_data = "\n".join(choices)

            process = subprocess.Popen(  # nosec B603
                fzf_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )

            stdout_bytes, _ = process.communicate(input=input_data.encode("utf-8"))
            result_code = process.returncode

            # User cancelled (ESC or Ctrl+C)
            if result_code in (1, 130):
                break

            if result_code != 0:
                print(f"Error running fzf: exit code {result_code}")
                break

            stdout = stdout_bytes.decode("utf-8", errors="replace")

            # Parse output: first line is the key pressed, second is the selection
            # NOTE: Don't strip before split - we need to preserve empty first line for Enter key
            lines = stdout.split("\n")
            if len(lines) < 2:
                # No selection made
                break

            key_pressed = lines[0].strip()
            selected_display = lines[1].strip()

            if not selected_display:
                break

            # Map display back to metadata
            selected = display_to_meta.get(selected_display, selected_display)

            # Handle Space to toggle settings
            if key_pressed == "space" and selected.startswith("__SETTING__"):
                # Parse: __SETTING__:setting_id:DESC||description\t\tdisplay
                metadata = selected.split("\t\t")[0]
                # Extract setting_id (second part before DESC)
                parts = metadata.split(":", 2)
                if len(parts) >= 2:
                    setting_id = parts[1].split(":")[0]  # Get just the ID before DESC
                    config = _toggle_setting(config, setting_id)
                    config_manager.save(config)
                    changes_made = True
                continue

            # Handle Enter to open actions/sub-menus or exit
            if key_pressed == "":
                # Back button - exit
                if selected.startswith("__BACK__"):
                    break

                # Action items - open sub-menu
                if selected.startswith("__ACTION__"):
                    # Use unique IDs to identify actions
                    if "ADD_GLOBAL_FILES" in selected:
                        from ai_launcher.ui.shared_context import add_global_files

                        if add_global_files(config_manager, scan_paths):
                            print("\n✓ Global files added\n")
                            input("Press Enter to continue...")
                            changes_made = True
                        continue

                    if "REMOVE_GLOBAL_FILES" in selected:
                        from ai_launcher.ui.shared_context import remove_global_files

                        if remove_global_files(config_manager):
                            print("\n✓ Global files removed\n")
                            input("Press Enter to continue...")
                            changes_made = True
                        continue

                    # Unknown action - just continue
                    continue

                # Headers and other items - ignore Enter
                continue

        except FileNotFoundError:
            print("Error: fzf not found. Please install fzf.")
            return changes_made
        except Exception as e:
            print(f"Error in settings menu: {e}")
            return changes_made

    return changes_made


def _build_settings_choices(config: ConfigData) -> List[str]:
    """Build list of settings menu items with descriptions.

    Args:
        config: Current configuration

    Returns:
        List of formatted menu items with embedded descriptions
    """
    choices = []

    # Cleanup section header
    choices.append("__HEADER__\t\t\033[1m🧹 Cleanup Settings\033[0m")

    # Cleanup enabled (master switch)
    enabled_icon = "✓" if config.cleanup.enabled else "✗"
    enabled_color = "\033[32m" if config.cleanup.enabled else "\033[90m"
    enabled_desc = "CLEANUP_ENABLED||Master switch for pre-launch cleanup. When disabled, no cleanup operations run.".replace(
        "\n", "\\n"
    )
    choices.append(
        f"__SETTING__:cleanup_enabled:{enabled_desc}\t\t{enabled_color}[{enabled_icon}] Auto-cleanup before launch\033[0m"
    )

    # Provider-specific cleanup (always safe)
    if config.cleanup.enabled:
        provider_icon = "✓" if config.cleanup.clean_provider_files else "✗"
        provider_color = (
            "\033[32m" if config.cleanup.clean_provider_files else "\033[90m"
        )
        provider_desc = "CLEAN_PROVIDER||Remove provider-specific files:\\n• .claude.json.backup.* files (bug workaround)\\n• Debug logs older than 7 days\\n• Old CLI versions\\n\\nSafe: Only affects AI provider files"
        choices.append(
            f"__SETTING__:clean_provider_files:{provider_desc}\t\t    {provider_color}[{provider_icon}] Clean provider files\033[0m \033[2m(backups, logs, old versions)\033[0m"
        )

        # System-wide cache (WARNING)
        cache_icon = "✓" if config.cleanup.clean_system_cache else "✗"
        cache_color = "\033[33m" if config.cleanup.clean_system_cache else "\033[90m"
        cache_warning = (
            "\033[2m(WARNING: affects all apps)\033[0m"
            if config.cleanup.clean_system_cache
            else "\033[2m(system-wide)\033[0m"
        )
        cache_desc = "CLEAN_CACHE||⚠️  WARNING: System-wide operation\\n\\nClears entire ~/.cache directory, which affects:\\n• All applications, not just AI tools\\n• VS Code, browsers, build tools, etc.\\n• Apps will rebuild cache (performance hit)\\n\\nRecommended: Keep disabled unless you know what you're doing"
        choices.append(
            f"__SETTING__:clean_system_cache:{cache_desc}\t\t    {cache_color}[{cache_icon}] Clean ~/.cache\033[0m {cache_warning}"
        )

        # npm cache (WARNING)
        npm_icon = "✓" if config.cleanup.clean_npm_cache else "✗"
        npm_color = "\033[33m" if config.cleanup.clean_npm_cache else "\033[90m"
        npm_warning = (
            "\033[2m(WARNING: slows npm installs)\033[0m"
            if config.cleanup.clean_npm_cache
            else "\033[2m(optional)\033[0m"
        )
        npm_desc = "CLEAN_NPM||⚠️  WARNING: Affects npm performance\\n\\nRuns 'npm cache clean --force' which:\\n• Clears downloaded npm packages (~/.npm)\\n• Can reach 800MB+ but is regenerated\\n• Slows down future npm install commands\\n• Unrelated to AI launcher functionality\\n\\nRecommended: Keep disabled unless disk space is critical"
        choices.append(
            f"__SETTING__:clean_npm_cache:{npm_desc}\t\t    {npm_color}[{npm_icon}] Clean npm cache\033[0m {npm_warning}"
        )

    # Spacing before next section
    choices.append("__HEADER__\t\t")

    # Global Files section
    choices.append("__HEADER__\t\t\033[1m🌐 Global Files\033[0m")

    add_files_desc = "ADD_GLOBAL_FILES||Add files to be loaded across all projects:\\n• Browse markdown files in your projects\\n• Select files containing standards, patterns, rules\\n• These will be available to AI in every project"
    choices.append(f"__ACTION__:{add_files_desc}\t\t➕ Add global files")

    remove_files_desc = "REMOVE_GLOBAL_FILES||Remove files from global context:\\n• Shows your currently configured global files\\n• Select files to remove from the list\\n• They'll no longer load automatically"
    choices.append(f"__ACTION__:{remove_files_desc}\t\t➖ Remove global files")

    # Spacing before back button
    choices.append("__HEADER__\t\t")

    # Back button
    back_desc = "BACK||Return to the project selector"
    choices.append(f"__BACK__:{back_desc}\t\t← Back to project selector")

    return choices


def _toggle_setting(config: ConfigData, setting_id: str) -> ConfigData:
    """Toggle a boolean setting.

    Args:
        config: Current configuration
        setting_id: ID of setting to toggle

    Returns:
        Updated configuration
    """
    if setting_id == "cleanup_enabled":
        config.cleanup.enabled = not config.cleanup.enabled
    elif setting_id == "clean_provider_files":
        config.cleanup.clean_provider_files = not config.cleanup.clean_provider_files
    elif setting_id == "clean_system_cache":
        config.cleanup.clean_system_cache = not config.cleanup.clean_system_cache
    elif setting_id == "clean_npm_cache":
        config.cleanup.clean_npm_cache = not config.cleanup.clean_npm_cache

    return config
