"""GitHub Copilot CLI provider implementation.

This module implements the AIProvider interface for GitHub Copilot CLI,
GitHub's AI-powered coding assistant for the terminal.

Installation:
    See https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli

Documentation:
    https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli

Author: Solent Labs™
Created: 2026-03-03
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


class CopilotProvider(AIProvider):
    """GitHub Copilot CLI provider implementation.

    GitHub Copilot CLI is a terminal-based AI coding assistant that integrates
    with GitHub's Copilot service.

    Installation:
        See https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli

    Documentation:
        https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli
    """

    @property
    def metadata(self) -> ProviderMetadata:
        """Get Copilot metadata.

        Returns:
            ProviderMetadata with Copilot-specific configuration
        """
        return ProviderMetadata(
            name="copilot",
            display_name="GitHub Copilot CLI",
            command="copilot",
            description="GitHub's AI coding assistant for the terminal",
            config_files=[".github/copilot-instructions.md", "AGENTS.md"],
            requires_installation=True,
        )

    def is_installed(self) -> bool:
        """Check if GitHub Copilot CLI is installed.

        Returns:
            True if 'copilot' command is available in PATH
        """
        return shutil.which("copilot") is not None

    def launch(self, project_path: Path) -> None:
        """Launch GitHub Copilot CLI in the specified project directory.

        Args:
            project_path: Path to the project directory

        Raises:
            FileNotFoundError: If Copilot CLI is not found
            subprocess.CalledProcessError: If Copilot fails to launch
        """
        # Change to project directory
        os.chdir(project_path)

        # Launch Copilot
        try:
            subprocess.run(["copilot"], check=True)  # nosec B603, B607
        except FileNotFoundError:
            print("Error: 'copilot' command not found.")
            print(
                "Install: https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli"
            )
            print(
                "Docs: https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli"
            )
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error launching Copilot: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            sys.exit(0)

    def cleanup_environment(
        self, verbose: bool = False, cleanup_config: Optional["CleanupConfig"] = None
    ) -> None:
        """Clean Copilot-specific environment.

        Clears Copilot cache directory if it exists and cleanup is enabled.

        Args:
            verbose: Whether to print cleanup messages to stdout
            cleanup_config: Configuration controlling what gets cleaned.
                          If None or disabled, no cleanup is performed.
        """
        # Only clean if config is provided and cleanup is enabled
        if cleanup_config is None or not cleanup_config.enabled:
            return

        # Only clean Copilot cache if provider-specific cleanup is enabled
        if not cleanup_config.clean_provider_files:
            return

        # Copilot stores config in ~/.config/github-copilot
        copilot_dir = Path.home() / ".config" / "github-copilot"
        if copilot_dir.exists():
            cache_dir = copilot_dir / "cache"
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    if verbose:
                        print("  → Cleaned Copilot cache")
                except (OSError, PermissionError):
                    pass  # Silently skip on error

    # === Data Collection (returns structured data) ===

    def collect_preview_data(self, project_path: Path) -> ProviderPreviewData:
        """Collect Copilot-specific preview data.

        Returns structured data only - no formatting.

        Args:
            project_path: Path to the project

        Returns:
            ProviderPreviewData with Copilot-specific information
        """
        context_files = []

        # Check for .github/copilot-instructions.md in project
        copilot_instructions = project_path / ".github" / "copilot-instructions.md"
        if copilot_instructions.exists():
            try:
                stat = copilot_instructions.stat()
                with open(copilot_instructions, encoding="utf-8") as f:
                    lines = f.readlines()
                    context_files.append(
                        ContextFile(
                            path=copilot_instructions,
                            label=".github/copilot-instructions.md",
                            exists=True,
                            size_bytes=stat.st_size,
                            line_count=len(lines),
                            file_type="project",
                            content_preview="".join(lines[:10]),
                        )
                    )
            except (OSError, UnicodeDecodeError):
                pass

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

        # Global config paths
        global_paths = self.get_global_context_paths()

        return ProviderPreviewData(
            provider_name=self.metadata.display_name,
            context_files=context_files,
            global_config_paths=global_paths,
        )

    # === Discovery Methods ===

    def get_global_context_paths(self) -> List[Path]:
        """Get paths to Copilot's global configuration."""
        return [
            Path.home() / ".config" / "github-copilot",
        ]

    def get_documentation_urls(self) -> Dict[str, str]:
        """Get GitHub Copilot CLI documentation URLs."""
        return {
            "Documentation": "https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli",
            "Installation": "https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli",
            "Custom instructions": "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions",
        }
