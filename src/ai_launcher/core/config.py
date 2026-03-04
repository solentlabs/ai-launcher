"""Configuration management for ai-launcher.

This module handles loading, saving, and validating configuration from TOML files.
It manages scan paths, UI preferences, provider selection, and cleanup settings.

Author: Solent Labs™
Last Modified: 2026-02-10 (Added cleanup config support)
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from platformdirs import user_config_path, user_data_path

from ai_launcher.utils.paths import expand_path

# Handle TOML parsing for different Python versions
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

import tomli_w

from ai_launcher.core.models import (
    CleanupConfig,
    ConfigData,
    ContextConfig,
    HistoryConfig,
    ProviderConfig,
    ScanConfig,
    UIConfig,
)


class ConfigManager:
    """Manages configuration loading, saving, and validation."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.

        Args:
            config_path: Optional path to config file. If None, uses platform default.
        """
        if config_path is None:
            self.config_path = user_config_path("ai-launcher") / "config.toml"
        else:
            self.config_path = config_path

        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> ConfigData:
        """Load configuration from file.

        Returns:
            ConfigData instance with loaded or default values

        Raises:
            RuntimeError: If tomli/tomllib is not available
        """
        if not self.config_path.exists():
            return self._get_defaults()

        if tomllib is None:
            raise RuntimeError(
                "TOML parsing not available. Install tomli: pip install tomli"
            )

        try:
            with open(self.config_path, "rb") as f:
                data = tomllib.load(f)
                return self._parse_config(data)
        except Exception as e:
            print(f"Warning: Error loading config: {e}")
            print("Falling back to defaults")
            return self._get_defaults()

    def save(self, config: ConfigData) -> None:
        """Save configuration to file.

        Args:
            config: ConfigData to save
        """
        data = self._config_to_dict(config)

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "wb") as f:
            tomli_w.dump(data, f)

    def _get_defaults(self) -> ConfigData:
        """Get default configuration.

        Returns:
            ConfigData with sensible defaults
        """
        return ConfigData(
            scan=ScanConfig(
                paths=[],
                max_depth=5,
            ),
            ui=UIConfig(
                preview_width=70,
                show_git_status=True,
                set_terminal_title=True,
                terminal_title_format="{project} → {provider}",
            ),
            history=HistoryConfig(
                max_entries=50,
            ),
        )

    def _parse_config(self, data: Dict[str, Any]) -> ConfigData:
        """Parse TOML data into ConfigData.

        Args:
            data: Raw TOML dictionary

        Returns:
            Parsed ConfigData instance
        """
        # Parse scan config
        scan_data = data.get("scan", {})
        scan_paths = [self._expand_path(p) for p in scan_data.get("paths", [])]
        scan = ScanConfig(
            paths=scan_paths,
            max_depth=scan_data.get("max_depth", 5),
            prune_dirs=scan_data.get(
                "prune_dirs",
                [
                    "node_modules",
                    ".cache",
                    "venv",
                    "__pycache__",
                    ".git",
                    ".venv",
                    "env",
                    "ENV",
                ],
            ),
        )

        # Parse UI config
        ui_data = data.get("ui", {})
        ui = UIConfig(
            preview_width=ui_data.get("preview_width", 70),
            show_git_status=ui_data.get("show_git_status", True),
            set_terminal_title=ui_data.get("set_terminal_title", True),
            terminal_title_format=ui_data.get(
                "terminal_title_format", "{project} → {provider}"
            ),
        )

        # Parse history config
        history_data = data.get("history", {})
        history = HistoryConfig(
            max_entries=history_data.get("max_entries", 50),
        )

        # Parse provider config
        provider_data = data.get("provider", {})
        provider = ProviderConfig(
            default=provider_data.get("default", "claude-code"),
            per_project=provider_data.get("per_project", {}),
        )

        # Parse context config
        context_data = data.get("context", {})
        context = ContextConfig(
            global_files=context_data.get("global_files", []),
        )

        # Parse cleanup config
        cleanup_data = data.get("cleanup", {})
        cleanup = CleanupConfig(
            enabled=cleanup_data.get("enabled", False),
            clean_provider_files=cleanup_data.get("clean_provider_files", True),
            clean_system_cache=cleanup_data.get("clean_system_cache", False),
            clean_npm_cache=cleanup_data.get("clean_npm_cache", False),
            debug_logs_max_age_days=cleanup_data.get("debug_logs_max_age_days", 7),
        )

        return ConfigData(
            scan=scan,
            ui=ui,
            history=history,
            provider=provider,
            context=context,
            cleanup=cleanup,
        )

    def _config_to_dict(self, config: ConfigData) -> Dict[str, Any]:
        """Convert ConfigData to dictionary for TOML serialization.

        Args:
            config: ConfigData to convert

        Returns:
            Dictionary suitable for TOML serialization
        """
        return {
            "scan": {
                "paths": [str(p) for p in config.scan.paths],
                "max_depth": config.scan.max_depth,
                "prune_dirs": config.scan.prune_dirs,
            },
            "ui": {
                "preview_width": config.ui.preview_width,
                "show_git_status": config.ui.show_git_status,
                "set_terminal_title": config.ui.set_terminal_title,
                "terminal_title_format": config.ui.terminal_title_format,
            },
            "history": {
                "max_entries": config.history.max_entries,
            },
            "provider": {
                "default": config.provider.default,
                "per_project": config.provider.per_project,
            },
            "context": {
                "global_files": config.context.global_files,
            },
            "cleanup": {
                "enabled": config.cleanup.enabled,
                "clean_provider_files": config.cleanup.clean_provider_files,
                "clean_system_cache": config.cleanup.clean_system_cache,
                "clean_npm_cache": config.cleanup.clean_npm_cache,
                "debug_logs_max_age_days": config.cleanup.debug_logs_max_age_days,
            },
        }

    def _expand_path(self, path_str: str) -> Path:
        """Expand path with ~ and environment variables.

        Args:
            path_str: Path string to expand

        Returns:
            Expanded Path object
        """
        return expand_path(path_str)

    def run_first_time_setup(self) -> ConfigData:
        """Run interactive first-time setup wizard.

        Returns:
            ConfigData with user-provided values
        """
        try:
            print("=== AI Launcher First-Time Setup ===\n")

            # Get scan paths
            paths = []
            print("Enter directories to scan for projects (one per line).")
            print("Common examples: ~/projects, ~/work, ~/code")
            print("Press Enter on empty line when done.\n")

            while True:
                path_input = input("Directory path: ").strip()
                if not path_input:
                    break

                try:
                    expanded_path = self._expand_path(path_input)
                    if not expanded_path.exists():
                        print(f"  Warning: {expanded_path} does not exist")
                        confirm = input("  Add anyway? (y/n): ").strip().lower()
                        if confirm != "y":
                            continue

                    paths.append(expanded_path)
                    print(f"  Added: {expanded_path}")
                except Exception as e:
                    print(f"  Error: {e}")

            if not paths:
                print(
                    "\nNo paths added. Pass a scan directory as argument when launching."
                )

            # Create config
            config = self._get_defaults()
            config.scan.paths = paths

            # Save config
            self.save(config)
            print(f"\nConfiguration saved to: {self.config_path}")

            return config

        except KeyboardInterrupt:
            print("\n\nSetup cancelled.")
            import sys

            sys.exit(0)


def get_data_dir() -> Path:
    """Get the data directory for ai-launcher.

    Returns:
        Path to data directory (for database, cache, etc.)
    """
    data_dir = Path(user_data_path("ai-launcher"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_database_path() -> Path:
    """Get the path to the SQLite database.

    Returns:
        Path to database file
    """
    data_dir = get_data_dir()
    return data_dir / "projects.db"
