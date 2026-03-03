"""Provider discovery for detecting and analyzing AI providers.

Uses ProviderRegistry for dynamic provider detection instead of hardcoded lists.

Author: Solent Labs™
Created: 2026-02-09
Updated: 2026-02-12 (Refactored to use ProviderRegistry)
"""

import re
import subprocess  # nosec B404
from pathlib import Path
from typing import Dict, List, Optional

from ai_launcher.core.context_analyzer import ContextAnalyzer
from ai_launcher.core.models import ProviderContext, ProviderInfo
from ai_launcher.providers.registry import ProviderRegistry
from ai_launcher.utils.logging import get_logger

logger = get_logger(__name__)


class ProviderDiscovery:
    """Discovers and analyzes AI providers on the system.

    This class detects installed AI providers, gets version information,
    and analyzes the context files they access. It uses ProviderRegistry
    to dynamically discover all available providers instead of maintaining
    a hardcoded list.
    """

    def __init__(self):
        """Initialize the provider discovery system."""
        self.analyzer = ContextAnalyzer()
        self.registry = ProviderRegistry()

    def detect_all(self) -> List[ProviderInfo]:
        """Detect all registered providers.

        Uses ProviderRegistry to discover providers dynamically.

        Returns:
            List of ProviderInfo objects with detection results
        """
        results = []
        for provider in self.registry.list_all():
            info = self._detect_provider(provider)
            results.append(info)
        return results

    def _detect_provider(self, provider) -> ProviderInfo:
        """Detect a single provider.

        Args:
            provider: AIProvider instance from registry

        Returns:
            ProviderInfo with detection results
        """
        metadata = provider.metadata

        # Check if installed
        if not provider.is_installed():
            # Get config paths for detection info
            try:
                config_paths = provider.get_global_context_paths()
            except (AttributeError, NotImplementedError):
                config_paths = []

            return ProviderInfo(
                name=metadata.display_name,
                command=metadata.command,
                context=None,
                install_url=None,  # Could add to metadata if needed
                detection_paths=config_paths,
            )

        # Get version
        version = self._get_version(metadata.command)

        # Analyze context
        context = self._analyze_context(provider, version)

        return ProviderInfo(
            name=metadata.display_name,
            command=metadata.command,
            context=context,
            install_url=None,
            detection_paths=[],
        )

    def _get_version(self, command: str) -> Optional[str]:
        """Get version string for a provider command.

        Args:
            command: CLI command to execute

        Returns:
            Version string if available, None otherwise
        """
        try:
            result = subprocess.run(
                [command, "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )  # nosec B603, B607

            if result.returncode == 0:
                return self._extract_version(result.stdout)

        except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.debug(f"Could not get version for {command}: {e}")

        return None

    def _extract_version(self, version_output: str) -> Optional[str]:
        """Extract version number from command output.

        Args:
            version_output: Output from --version command

        Returns:
            Version string (e.g., "2.1.37") if found, None otherwise
        """
        # Try to match standard version patterns: X.Y.Z
        match = re.search(r"(\d+\.\d+\.\d+)", version_output)
        if match:
            return match.group(1)

        return None

    def _analyze_context(
        self, provider, version: Optional[str]
    ) -> ProviderContext:
        """Analyze context for a provider.

        Args:
            provider: AIProvider instance
            version: Provider version string

        Returns:
            ProviderContext with analysis results
        """
        import shutil

        metadata = provider.metadata

        # Get executable path
        executable_path = shutil.which(metadata.command)

        # Get global config paths from provider
        try:
            config_paths = provider.get_global_context_paths()
        except (AttributeError, NotImplementedError):
            config_paths = []

        # Find existing global config files
        global_config = []
        for config_path in config_paths:
            if config_path.exists():
                global_config.append(config_path)

        # Categorize files in config directories
        all_categories: Dict[str, List[Path]] = {
            cat: [] for cat in self.analyzer.CATEGORIES.keys()
        }
        all_categories["other"] = []

        for config_path in global_config:
            if config_path.is_dir():
                # Categorize files in directory
                categories = self.analyzer.categorize_directory(config_path)

                # Merge categories
                for cat, files in categories.items():
                    all_categories[cat].extend(files)

        # Calculate stats
        file_count, total_size = self.analyzer.get_total_stats(all_categories)

        # Get project data pattern from provider if available
        try:
            project_pattern = provider.get_project_data_pattern()
        except (AttributeError, NotImplementedError):
            project_pattern = None

        return ProviderContext(
            name=metadata.display_name,
            version=version,
            installed=True,
            executable_path=Path(executable_path) if executable_path else None,
            global_config=global_config,
            project_data_pattern=project_pattern,
            categories=all_categories,
            total_size=total_size,
            file_count=file_count,
        )

    def get_installed_providers(self) -> List[ProviderInfo]:
        """Get only installed providers.

        Returns:
            List of ProviderInfo for installed providers
        """
        all_providers = self.detect_all()
        return [p for p in all_providers if p.context is not None]

    def get_provider_by_name(self, name: str) -> Optional[ProviderInfo]:
        """Get provider info by name.

        Args:
            name: Provider display name (e.g., "Claude Code")

        Returns:
            ProviderInfo if found, None otherwise
        """
        all_providers = self.detect_all()
        for provider in all_providers:
            if provider.name == name:
                return provider
        return None
