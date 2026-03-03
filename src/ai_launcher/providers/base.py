"""Base classes for AI provider abstraction.

This module defines the abstract base class and metadata structures that all
AI provider implementations must follow.

Author: Solent Labs™
Created: 2026-02-09
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from ai_launcher.utils.terminal import format_terminal_title, set_terminal_title

if TYPE_CHECKING:
    from ai_launcher.core.models import CleanupConfig
    from ai_launcher.core.provider_data import ProviderPreviewData


@dataclass
class ProviderMetadata:
    """Metadata about an AI provider.

    Attributes:
        name: Internal identifier (e.g., "claude-code")
        display_name: Human-readable name (e.g., "Claude Code")
        command: CLI command to execute (e.g., "claude")
        description: Brief description of the provider
        config_files: List of config files the provider uses (e.g., ["CLAUDE.md"])
        requires_installation: Whether installation check is needed
    """

    name: str
    display_name: str
    command: str
    description: str
    config_files: List[str] = field(default_factory=list)
    requires_installation: bool = True


class AIProvider(ABC):
    """Abstract base class for AI provider implementations.

    All AI provider implementations (Claude, Gemini, etc.) must inherit from
    this class and implement its abstract methods. This ensures a consistent
    interface for launching different AI tools.

    Example:
        >>> class MyProvider(AIProvider):
        ...     @property
        ...     def metadata(self) -> ProviderMetadata:
        ...         return ProviderMetadata(
        ...             name="my-ai",
        ...             display_name="My AI",
        ...             command="myai",
        ...             description="My AI assistant",
        ...         )
        ...
        ...     def is_installed(self) -> bool:
        ...         return shutil.which("myai") is not None
        ...
        ...     def launch(self, project_path: Path) -> None:
        ...         os.chdir(project_path)
        ...         subprocess.run(["myai"], check=True)
        ...
        ...     def cleanup_environment(self, verbose: bool = False) -> None:
        ...         # Clean provider-specific cache/data
        ...         pass
    """

    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        """Get provider metadata.

        Returns:
            ProviderMetadata instance describing this provider
        """
        pass

    @abstractmethod
    def is_installed(self) -> bool:
        """Check if provider CLI is available on the system.

        Returns:
            True if the provider's CLI command is installed and accessible
        """
        pass

    @abstractmethod
    def launch(self, project_path: Path) -> None:
        """Launch AI tool in the specified project directory.

        Args:
            project_path: Path to the project directory to launch in

        Raises:
            FileNotFoundError: If provider CLI is not found
            subprocess.CalledProcessError: If provider CLI fails to launch
        """
        pass

    @abstractmethod
    def cleanup_environment(
        self, verbose: bool = False, cleanup_config: Optional["CleanupConfig"] = None
    ) -> None:
        """Clean provider-specific environment before launching.

        This should clean provider-specific cache, logs, and temporary files
        to maintain a clean development environment.

        Args:
            verbose: Whether to print cleanup messages to stdout
            cleanup_config: Configuration controlling what gets cleaned.
                          If None or disabled, no cleanup is performed.
        """
        pass

    def get_context_sources(self, project_path: Path) -> List[Path]:
        """Get context files the provider reads from the project.

        Default implementation checks for config files listed in metadata.
        Providers can override this for more complex context discovery.

        Args:
            project_path: Path to the project directory

        Returns:
            List of paths to context files that exist
        """
        return [
            project_path / filename
            for filename in self.metadata.config_files
            if (project_path / filename).exists()
        ]

    def get_global_context_paths(self) -> List[Path]:
        """Get paths to provider's global configuration.

        Default implementation returns empty list.
        Providers should override to specify their global config paths.

        Returns:
            List of paths to global config files/directories
        """
        return []

    def get_project_data_pattern(self) -> Optional[str]:
        """Get pattern for provider's project data storage.

        Default implementation returns None.
        Providers can override to specify where they store project data.

        Returns:
            String pattern describing project data location, or None
        """
        return None

    def get_context_categories(self) -> dict:
        """Get provider-specific file categorization patterns.

        Default implementation returns empty dict.
        Providers can override to provide custom file categories.

        Returns:
            Dictionary mapping category names to file patterns
        """
        return {}

    def collect_preview_data(self, project_path: Path) -> "ProviderPreviewData":
        """Collect provider-specific preview data.

        Default implementation scans for config files listed in metadata.
        Providers should override this for richer data collection.

        Args:
            project_path: Path to the project

        Returns:
            ProviderPreviewData with basic information
        """
        from ai_launcher.core.provider_data import ContextFile, ProviderPreviewData

        context_files = []
        for filename in self.metadata.config_files:
            file_path = project_path / filename
            if file_path.exists():
                try:
                    stat = file_path.stat()
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    context_files.append(
                        ContextFile(
                            path=file_path,
                            label=filename,
                            exists=True,
                            size_bytes=stat.st_size,
                            line_count=len(lines),
                            file_type="project",
                            content_preview="".join(lines[:10]),
                        )
                    )
                except (OSError, UnicodeDecodeError):
                    context_files.append(
                        ContextFile(path=file_path, label=filename, exists=False)
                    )
            else:
                context_files.append(
                    ContextFile(path=file_path, label=filename, exists=False)
                )

        return ProviderPreviewData(
            provider_name=self.metadata.display_name,
            context_files=context_files,
            global_config_paths=self.get_global_context_paths(),
        )

    def get_documentation_urls(self) -> Dict[str, str]:
        """Get provider documentation URLs.

        Returns a dictionary mapping topic names to URLs.
        Providers should override to provide their own docs.

        Returns:
            Dictionary of topic -> URL mappings
        """
        return {}

    def launch_with_title(
        self,
        project_path: Path,
        set_title: bool = True,
        title_format: str = "{project} → {provider}",
    ) -> None:
        """Launch provider with optional terminal title setting.

        This is a convenience wrapper around launch() that optionally sets the
        terminal title before launching the provider.

        Args:
            project_path: Path to the project directory to launch in
            set_title: Whether to set terminal title before launching
            title_format: Format string for terminal title
                         Available variables: {project}, {provider}, {path}, {parent}

        Raises:
            FileNotFoundError: If provider CLI is not found
            subprocess.CalledProcessError: If provider CLI fails to launch
        """
        # Set terminal title if requested
        if set_title:
            title = format_terminal_title(
                title_format,
                project_path,
                self.metadata.display_name,
            )
            set_terminal_title(title)

        # Launch provider
        self.launch(project_path)
