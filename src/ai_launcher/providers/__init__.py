"""AI provider abstraction layer for ai-launcher.

This package provides the provider abstraction system that allows ai-launcher
to support multiple AI coding assistants (Claude Code, Gemini, etc.).

Author: Solent Labs™
Created: 2026-02-09
"""

from ai_launcher.providers.base import AIProvider, ProviderMetadata
from ai_launcher.providers.registry import get_provider, get_registry

__all__ = [
    "AIProvider",
    "ProviderMetadata",
    "get_provider",
    "get_registry",
]
