"""Gemini CLI provider implementation.

This module implements the AIProvider interface for Google's Gemini AI assistant.

Installation:
    npm install -g @google/gemini-cli

Documentation:
    https://geminicli.com/docs/get-started/

Author: Solent Labs™
Created: 2026-02-09
"""

import os
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from ai_launcher.core.provider_data import ContextFile, ProviderPreviewData
from ai_launcher.providers.base import AIProvider, ProviderMetadata
from ai_launcher.utils.logging import get_logger

if TYPE_CHECKING:
    from ai_launcher.core.models import CleanupConfig

logger = get_logger(__name__)


class GeminiProvider(AIProvider):
    """Gemini CLI provider implementation.

    Provides integration with Google's Gemini AI assistant CLI tool.
    Note: This is a basic implementation and may need adjustments based on
    actual Gemini CLI behavior when it becomes available.
    """

    @property
    def metadata(self) -> ProviderMetadata:
        """Get Gemini metadata.

        Returns:
            ProviderMetadata with Gemini-specific configuration
        """
        return ProviderMetadata(
            name="gemini",
            display_name="Gemini CLI",
            command="gemini",
            description="Google's Gemini AI assistant",
            config_files=["GEMINI.md"],
            requires_installation=True,
        )

    def is_installed(self) -> bool:
        """Check if Gemini CLI is installed.

        Returns:
            True if 'gemini' command is available in PATH
        """
        return shutil.which("gemini") is not None

    def launch(self, project_path: Path) -> None:
        """Launch Gemini CLI in the specified project directory.

        Args:
            project_path: Path to the project directory

        Raises:
            FileNotFoundError: If Gemini CLI is not found
            subprocess.CalledProcessError: If Gemini fails to launch
        """
        # Change to project directory
        os.chdir(project_path)

        # Launch Gemini
        try:
            subprocess.run(["gemini"], check=True)  # nosec B603, B607
        except FileNotFoundError:
            print("Error: 'gemini' command not found.")
            print("Install: npm install -g @google/gemini-cli")
            print("Docs: https://geminicli.com/docs/get-started/")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error launching Gemini: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            sys.exit(0)

    def cleanup_environment(
        self, verbose: bool = False, cleanup_config: Optional["CleanupConfig"] = None
    ) -> None:
        """Clean Gemini-specific environment.

        Clears Gemini cache directory if it exists and cleanup is enabled.
        This is a minimal implementation - adjust based on actual Gemini behavior.

        Args:
            verbose: Whether to print cleanup messages to stdout
            cleanup_config: Configuration controlling what gets cleaned.
                          If None or disabled, no cleanup is performed.
        """
        # Only clean if config is provided and cleanup is enabled
        if cleanup_config is None or not cleanup_config.enabled:
            return

        # Only clean Gemini cache if provider-specific cleanup is enabled
        if not cleanup_config.clean_provider_files:
            return

        home = Path.home()
        gemini_cache = home / ".gemini" / "cache"

        if gemini_cache.exists() and gemini_cache.is_dir():
            try:
                shutil.rmtree(gemini_cache, ignore_errors=True)
                logger.debug("Cleaned Gemini cache directory")
                if verbose:
                    print("  → Cleaned Gemini cache")
            except (OSError, PermissionError) as e:
                logger.debug(f"Could not clean Gemini cache: {e}")

    # === NEW: Data Collection (returns structured data) ===

    def collect_preview_data(self, project_path: Path) -> ProviderPreviewData:
        """Collect Gemini-specific preview data.

        Returns structured data only - no formatting.
        This is a STUB implementation for now.

        Args:
            project_path: Path to the project

        Returns:
            ProviderPreviewData with Gemini-specific information
        """
        context_files = []

        # Check for GEMINI.md in project
        gemini_md = project_path / "GEMINI.md"
        if gemini_md.exists():
            try:
                stat = gemini_md.stat()
                with open(gemini_md, encoding="utf-8") as f:
                    lines = f.readlines()
                    context_files.append(
                        ContextFile(
                            path=gemini_md,
                            label="GEMINI.md",
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
        """Get paths to Gemini's global configuration."""
        return [
            Path.home() / ".gemini",
        ]

    def get_documentation_urls(self) -> Dict[str, str]:
        """Get Gemini documentation URLs."""
        return {
            "GEMINI.md guide": "https://geminicli.com/docs/cli/gemini-md/",
            "Getting started": "https://geminicli.com/docs/get-started/",
            "Installation": "https://geminicli.com/docs/get-started/installation/",
            "Configuration": "https://geminicli.com/docs/get-started/configuration/",
        }
