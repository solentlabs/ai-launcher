"""Cursor IDE provider implementation.

This module implements the AIProvider interface for Cursor, an AI-first
code editor built on VS Code.

Author: Solent Labs™
Created: 2026-02-10
"""

import os
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from ai_launcher.core.provider_data import ContextFile, ProviderPreviewData
from ai_launcher.providers.base import AIProvider, ProviderMetadata

if TYPE_CHECKING:
    from ai_launcher.core.models import CleanupConfig


class CursorProvider(AIProvider):
    """Cursor IDE provider implementation.

    Cursor is an AI-first code editor built as a fork of VS Code with
    integrated AI features including code generation, chat, and refactoring.

    Installation:
        Download from https://cursor.sh/

    Documentation:
        https://cursor.sh/docs
    """

    @property
    def metadata(self) -> ProviderMetadata:
        """Get Cursor metadata.

        Returns:
            ProviderMetadata with Cursor-specific configuration
        """
        return ProviderMetadata(
            name="cursor",
            display_name="Cursor",
            command="cursor",
            description="AI-first code editor",
            config_files=[".cursorrules", "CURSOR.md"],
            requires_installation=True,
        )

    def is_installed(self) -> bool:
        """Check if Cursor is installed.

        Returns:
            True if 'cursor' command is available in PATH
        """
        return shutil.which("cursor") is not None

    def launch(self, project_path: Path) -> None:
        """Launch Cursor in the specified project directory.

        Args:
            project_path: Path to the project directory

        Raises:
            FileNotFoundError: If Cursor CLI is not found
            subprocess.CalledProcessError: If Cursor fails to launch
        """
        # Cursor is an IDE, pass the directory path as argument
        try:
            subprocess.run(["cursor", str(project_path)], check=True)  # nosec B603, B607
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

        # Cursor stores data in platform-specific locations
        home = Path.home()
        cursor_dirs = [
            home / ".cursor",  # Linux
            home / ".config" / "Cursor",  # Linux XDG
            home / "Library" / "Application Support" / "Cursor",  # macOS
        ]

        for cursor_dir in cursor_dirs:
            if cursor_dir.exists():
                cache_dir = cursor_dir / "Cache"
                if cache_dir.exists():
                    try:
                        shutil.rmtree(cache_dir, ignore_errors=True)
                        if verbose:
                            print("  → Cleaned Cursor cache")
                        break  # Only clean once
                    except (OSError, PermissionError):
                        pass  # Silently skip on error

    # === NEW: Data Collection (returns structured data) ===

    def collect_preview_data(self, project_path: Path) -> ProviderPreviewData:
        """Collect Cursor-specific preview data.

        Returns structured data only - no formatting.
        This is a STUB implementation for now.

        Args:
            project_path: Path to the project

        Returns:
            ProviderPreviewData with Cursor-specific information
        """
        context_files = []

        # Check for .cursorrules in project
        cursorrules = project_path / ".cursorrules"
        if cursorrules.exists():
            try:
                stat = cursorrules.stat()
                with open(cursorrules, "r", encoding="utf-8") as f:
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

        # Check for CURSOR.md in project
        cursor_md = project_path / "CURSOR.md"
        if cursor_md.exists():
            try:
                stat = cursor_md.stat()
                with open(cursor_md, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    context_files.append(
                        ContextFile(
                            path=cursor_md,
                            label="CURSOR.md",
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
        home = Path.home()
        return [
            home / ".cursor",  # Linux
            home / ".config" / "Cursor",  # Linux XDG
            home / "Library" / "Application Support" / "Cursor",  # macOS
        ]
