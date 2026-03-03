"""Aider AI pair programming provider implementation.

This module implements the AIProvider interface for Aider, a terminal-based
AI pair programming tool.

Author: Solent Labs™
Created: 2026-02-10
"""

import os
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from ai_launcher.core.provider_data import ContextFile, ProviderPreviewData
from ai_launcher.providers.base import AIProvider, ProviderMetadata

if TYPE_CHECKING:
    from ai_launcher.core.models import CleanupConfig


class AiderProvider(AIProvider):
    """Aider provider implementation.

    Aider is a terminal-based AI pair programming tool that works with
    various LLMs (GPT-4, Claude, etc.) via API.

    Installation:
        pip install aider-chat

    Documentation:
        https://aider.chat/
    """

    @property
    def metadata(self) -> ProviderMetadata:
        """Get Aider metadata.

        Returns:
            ProviderMetadata with Aider-specific configuration
        """
        return ProviderMetadata(
            name="aider",
            display_name="Aider",
            command="aider",
            description="AI pair programming in the terminal",
            config_files=[".aider.conf.yml", "AIDER.md"],
            requires_installation=True,
        )

    def is_installed(self) -> bool:
        """Check if Aider is installed.

        Returns:
            True if 'aider' command is available in PATH
        """
        return shutil.which("aider") is not None

    def launch(self, project_path: Path) -> None:
        """Launch Aider in the specified project directory.

        Args:
            project_path: Path to the project directory

        Raises:
            FileNotFoundError: If Aider CLI is not found
            subprocess.CalledProcessError: If Aider fails to launch
        """
        # Change to project directory
        os.chdir(project_path)

        # Check for config file
        config_file = project_path / ".aider.conf.yml"
        cmd = ["aider"]
        if config_file.exists():
            cmd.extend(["--config", str(config_file)])

        # Launch Aider
        try:
            subprocess.run(cmd, check=True)  # nosec B603, B607
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
        """Clean Aider-specific environment.

        Clears Aider cache directory if it exists and cleanup is enabled.

        Args:
            verbose: Whether to print cleanup messages to stdout
            cleanup_config: Configuration controlling what gets cleaned.
                          If None or disabled, no cleanup is performed.
        """
        # Only clean if config is provided and cleanup is enabled
        if cleanup_config is None or not cleanup_config.enabled:
            return

        # Only clean Aider cache if provider-specific cleanup is enabled
        if not cleanup_config.clean_provider_files:
            return

        # Aider stores cache in ~/.aider
        aider_dir = Path.home() / ".aider"
        if aider_dir.exists():
            cache_dir = aider_dir / "cache"
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    if verbose:
                        print("  → Cleaned Aider cache")
                except (OSError, PermissionError):
                    pass  # Silently skip on error

    # === NEW: Data Collection (returns structured data) ===

    def collect_preview_data(self, project_path: Path) -> ProviderPreviewData:
        """Collect Aider-specific preview data.

        Returns structured data only - no formatting.
        This is a STUB implementation for now.

        Args:
            project_path: Path to the project

        Returns:
            ProviderPreviewData with Aider-specific information
        """
        context_files = []

        # Check for .aider.conf.yml in project
        aider_config = project_path / ".aider.conf.yml"
        if aider_config.exists():
            try:
                stat = aider_config.stat()
                with open(aider_config, encoding="utf-8") as f:
                    lines = f.readlines()
                    context_files.append(
                        ContextFile(
                            path=aider_config,
                            label=".aider.conf.yml",
                            exists=True,
                            size_bytes=stat.st_size,
                            line_count=len(lines),
                            file_type="project",
                            content_preview="".join(lines[:10]),
                        )
                    )
            except (OSError, UnicodeDecodeError):
                pass

        # Check for AIDER.md in project
        aider_md = project_path / "AIDER.md"
        if aider_md.exists():
            try:
                stat = aider_md.stat()
                with open(aider_md, encoding="utf-8") as f:
                    lines = f.readlines()
                    context_files.append(
                        ContextFile(
                            path=aider_md,
                            label="AIDER.md",
                            exists=True,
                            size_bytes=stat.st_size,
                            line_count=len(lines),
                            file_type="project",
                            content_preview="".join(lines[:10]),
                        )
                    )
            except (OSError, UnicodeDecodeError):
                pass

        # Global config paths
        global_paths = self.get_global_context_paths()

        return ProviderPreviewData(
            provider_name=self.metadata.display_name,
            context_files=context_files,
            global_config_paths=global_paths,
        )

    # === Discovery Methods ===

    def get_global_context_paths(self) -> List[Path]:
        """Get paths to Aider's global configuration."""
        return [
            Path.home() / ".aider",
        ]

    def get_documentation_urls(self) -> Dict[str, str]:
        """Get Aider documentation URLs."""
        return {
            "Documentation": "https://aider.chat/docs/",
            "Installation": "https://aider.chat/docs/install.html",
            "Configuration": "https://aider.chat/docs/config.html",
        }
