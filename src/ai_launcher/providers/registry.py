"""Provider registry for managing AI provider instances.

This module provides a centralized registry for AI providers, making it easy
to discover, access, and manage different AI provider implementations.

The registry uses auto-discovery to find all provider implementations in the
providers/ directory, eliminating the need for manual registration.

Author: Solent Labs™
Created: 2026-02-09
Updated: 2026-02-10 (Added auto-discovery)
"""

import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Optional

from ai_launcher.providers.base import AIProvider
from ai_launcher.utils.logging import get_logger

logger = get_logger(__name__)


class ProviderRegistry:
    """Registry of available AI providers with auto-discovery.

    The registry automatically discovers and registers all AIProvider
    implementations found in the providers/ directory. Simply add a new
    provider file (e.g., aider.py) and it will be automatically loaded.

    Example:
        >>> registry = ProviderRegistry()
        >>> provider = registry.get("claude-code")
        >>> if provider and provider.is_installed():
        ...     provider.launch(Path("/path/to/project"))

    Auto-Discovery:
        - Scans providers/ directory for .py files
        - Imports each module dynamically
        - Finds classes inheriting from AIProvider
        - Instantiates and registers them automatically
        - Skips modules: __init__, base, registry
        - Handles import errors gracefully
    """

    def __init__(self) -> None:
        """Initialize the registry and auto-discover providers."""
        self._providers: Dict[str, AIProvider] = {}

        # Auto-discover all provider implementations
        self._discover_providers()

    def _discover_providers(self) -> None:
        """Discover and register all provider implementations.

        Scans the providers/ directory for Python modules and automatically
        imports and registers any AIProvider subclasses found.

        This method:
        1. Finds the providers/ directory
        2. Scans for .py files (excluding special modules)
        3. Dynamically imports each module
        4. Finds AIProvider subclasses
        5. Instantiates and registers them

        Errors during import or instantiation are logged but don't stop
        discovery, allowing other providers to load successfully.
        """
        # Find providers directory
        providers_dir = Path(__file__).parent

        # Skip these modules (not provider implementations)
        skip_modules = {"__init__", "base", "registry"}

        discovered_count = 0
        error_count = 0

        # Scan for provider modules
        for module_file in sorted(providers_dir.glob("*.py")):
            module_name = module_file.stem

            # Skip special modules
            if module_name in skip_modules:
                continue

            # Import the module
            try:
                module_path = f"ai_launcher.providers.{module_name}"
                module = importlib.import_module(module_path)

                # Find AIProvider subclasses in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Check if it's an AIProvider subclass (but not AIProvider itself)
                    if (
                        issubclass(obj, AIProvider)
                        and obj is not AIProvider
                        and obj.__module__ == module_path  # Defined in this module
                    ):
                        try:
                            # Instantiate and register the provider
                            provider = obj()
                            self.register(provider)
                            discovered_count += 1
                            logger.debug(
                                f"Registered provider: {provider.metadata.name} "
                                f"({provider.metadata.display_name})"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to instantiate provider {name} "
                                f"from {module_name}: {e}"
                            )
                            error_count += 1

            except Exception as e:
                logger.warning(f"Failed to import provider module {module_name}: {e}")
                error_count += 1

        logger.debug(
            f"Provider discovery complete: {discovered_count} registered, "
            f"{error_count} errors"
        )

    def register(self, provider: AIProvider) -> None:
        """Register a provider in the registry.

        Args:
            provider: AIProvider instance to register
        """
        self._providers[provider.metadata.name] = provider

    def get(self, name: str) -> Optional[AIProvider]:
        """Get a provider by name.

        Args:
            name: Provider name (e.g., "claude-code")

        Returns:
            AIProvider instance if found, None otherwise
        """
        return self._providers.get(name)

    def list_all(self) -> List[AIProvider]:
        """List all registered providers.

        Returns:
            List of all AIProvider instances in the registry
        """
        return list(self._providers.values())

    def list_installed(self) -> List[AIProvider]:
        """List only installed providers.

        Returns:
            List of AIProvider instances that are installed on the system
        """
        return [p for p in self._providers.values() if p.is_installed()]

    def get_names(self) -> List[str]:
        """Get names of all registered providers.

        Returns:
            List of provider names
        """
        return list(self._providers.keys())


# Global registry instance
_registry: Optional[ProviderRegistry] = None


def get_registry() -> ProviderRegistry:
    """Get the global provider registry instance.

    Returns:
        Singleton ProviderRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def get_provider(name: str) -> AIProvider:
    """Get a provider by name with validation.

    This is a convenience function that validates provider existence and
    installation status.

    Args:
        name: Provider name (e.g., "claude-code")

    Returns:
        AIProvider instance

    Raises:
        ValueError: If provider is unknown or not installed
    """
    registry = get_registry()
    provider = registry.get(name)

    if not provider:
        available = ", ".join(registry.get_names())
        raise ValueError(f"Unknown provider: {name}\nAvailable providers: {available}")

    if not provider.is_installed():
        raise ValueError(
            f"Provider '{name}' ({provider.metadata.display_name}) is not installed.\n"
            f"Command '{provider.metadata.command}' not found in PATH."
        )

    return provider
