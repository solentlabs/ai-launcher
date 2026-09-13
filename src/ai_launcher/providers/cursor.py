"""Cursor CLI provider implementation.

This module implements the AIProvider interface for Cursor CLI, a terminal-based
AI coding agent from Cursor.

Installation:
    curl https://cursor.com/install -fsS | bash

Documentation:
    https://cursor.com/docs/cli/using

Author: Solent Labs™
Created: 2026-02-10
"""

import os
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence

from ai_launcher.core.provider_data import ContextFile, ProviderPreviewData
from ai_launcher.providers.base import AIProvider, ProviderMetadata

if TYPE_CHECKING:
    from ai_launcher.core.models import CleanupConfig


class CursorProvider(AIProvider):
    """Cursor CLI provider implementation.

    Cursor CLI is a terminal-based AI coding agent. The CLI command is 'agent'.
    It reads .cursor/rules/ directory and AGENTS.md for project context.

    Installation:
        curl https://cursor.com/install -fsS | bash

    Documentation:
        https://cursor.com/docs/cli/using
    """

    @property
    def metadata(self) -> ProviderMetadata:
        """Get Cursor CLI metadata.

        Returns:
            ProviderMetadata with Cursor CLI-specific configuration
        """
        return ProviderMetadata(
            name="cursor",
            display_name="Cursor CLI",
            command="agent",
            description="AI coding agent in the terminal",
            config_files=["AGENTS.md", ".cursorrules"],
            requires_installation=True,
        )

    def is_installed(self) -> bool:
        """Check if Cursor CLI is installed.

        Returns:
            True if 'agent' command is available in PATH
        """
        return shutil.which("agent") is not None

    def launch(self, project_path: Path, scope_roots: Sequence[Path] = ()) -> None:  # noqa: ARG002
        """Launch Cursor CLI in the specified project directory.

        Args:
            project_path: Path to the project directory
            scope_roots: Unused; see docs/project-scope.md for how this tool
                treats writes outside the project

        Raises:
            FileNotFoundError: If Cursor CLI is not found
            subprocess.CalledProcessError: If Cursor CLI fails to launch
        """
        # Change to project directory
        os.chdir(project_path)

        # Launch Cursor CLI
        try:
            subprocess.run(["agent"], check=True)  # nosec B603, B607
        except FileNotFoundError:
            print("Error: 'agent' command not found.")
            print("Install: curl https://cursor.com/install -fsS | bash")
            print("Docs: https://cursor.com/docs/cli/using")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error launching Cursor CLI: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            sys.exit(0)

    def cleanup_environment(
        self, verbose: bool = False, cleanup_config: Optional["CleanupConfig"] = None
    ) -> None:
        """Clean Cursor-specific environment.

        Clears Cursor cache directory if it exists and cleanup is enabled.

        Args:
            verbose: Whether to print cleanup messages to stdout
            cleanup_config: Configuration controlling what gets cleaned.
                          If None or disabled, no cleanup is performed.
        """
        # Only clean if config is provided and cleanup is enabled
        if cleanup_config is None or not cleanup_config.enabled:
            return

        # Only clean Cursor cache if provider-specific cleanup is enabled
        if not cleanup_config.clean_provider_files:
            return

        # Cursor stores data in ~/.cursor
        home = Path.home()
        cursor_dir = home / ".cursor"
        if cursor_dir.exists():
            cache_dir = cursor_dir / "cache"
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    if verbose:
                        print("  → Cleaned Cursor cache")
                except (OSError, PermissionError):
                    pass  # Silently skip on error

    # === Data Collection (returns structured data) ===

    def collect_preview_data(self, project_path: Path) -> ProviderPreviewData:
        """Collect Cursor CLI-specific preview data.

        Returns structured data only - no formatting.

        Args:
            project_path: Path to the project

        Returns:
            ProviderPreviewData with Cursor CLI-specific information
        """
        context_files = []

        # Check for AGENTS.md in project
        agents_md = project_path / "AGENTS.md"
        if agents_md.exists():
            try:
                stat = agents_md.stat()
                with open(agents_md, encoding="utf-8") as f:
                    lines = f.readlines()
                    context_files.append(
                        ContextFile(
                            path=agents_md,
                            label="AGENTS.md",
                            exists=True,
                            size_bytes=stat.st_size,
                            line_count=len(lines),
                            file_type="project",
                            content_preview="".join(lines[:10]),
                        )
                    )
            except (OSError, UnicodeDecodeError):
                pass

        # Check for .cursorrules in project (legacy, still supported)
        cursorrules = project_path / ".cursorrules"
        if cursorrules.exists():
            try:
                stat = cursorrules.stat()
                with open(cursorrules, encoding="utf-8") as f:
                    lines = f.readlines()
                    context_files.append(
                        ContextFile(
                            path=cursorrules,
                            label=".cursorrules",
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
        """Get paths to Cursor's global configuration."""
        return [
            Path.home() / ".cursor",
        ]

    def get_documentation_urls(self) -> Dict[str, str]:
        """Get Cursor CLI documentation URLs."""
        return {
            "Documentation": "https://cursor.com/docs/cli/using",
            "Installation": "https://cursor.com/cli",
            "Rules": "https://cursor.com/docs/context/rules",
        }
