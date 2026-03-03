"""Context analyzer for categorizing and analyzing provider context files.

Author: Solent Labs™
Created: 2026-02-09
"""

from pathlib import Path
from typing import Dict, List

from ai_launcher.utils.logging import get_logger

logger = get_logger(__name__)


class ContextAnalyzer:
    """Analyzes and categorizes context files accessed by AI providers.

    The analyzer categorizes files based on their names and paths into
    logical categories like config, credentials, logs, cache, etc.
    """

    # Category definitions with detection patterns
    CATEGORIES = {
        "config": [".json", ".toml", ".yaml", ".yml", ".rc", "config"],
        "credentials": ["credential", "oauth", "token", "auth", "key"],
        "logs": ["debug", ".log", "logs"],
        "cache": ["cache", "downloads", "tmp"],
        "history": ["history"],
        "projects": ["projects"],
        "executables": ["versions", "bin", "exe"],
    }

    def categorize_directory(self, path: Path) -> Dict[str, List[Path]]:
        """Categorize all files in a directory.

        Args:
            path: Path to directory to analyze

        Returns:
            Dictionary mapping category names to lists of file paths
        """
        # Initialize categories
        categories: Dict[str, List[Path]] = {cat: [] for cat in self.CATEGORIES.keys()}
        categories["other"] = []

        if not path.exists():
            logger.debug(f"Path does not exist: {path}")
            return categories

        if not path.is_dir():
            logger.debug(f"Path is not a directory: {path}")
            return categories

        # Walk the directory tree
        try:
            for item in path.rglob("*"):
                if not item.is_file():
                    continue

                categorized = False
                item_lower = str(item).lower()
                name_lower = item.name.lower()

                # Try to match against category patterns
                for category, patterns in self.CATEGORIES.items():
                    for pattern in patterns:
                        if pattern in name_lower or pattern in item_lower:
                            categories[category].append(item)
                            categorized = True
                            break
                    if categorized:
                        break

                # If no category matched, put in "other"
                if not categorized:
                    categories["other"].append(item)

        except (OSError, PermissionError) as e:
            logger.debug(f"Error scanning directory {path}: {e}")

        return categories

    def calculate_sizes(self, categories: Dict[str, List[Path]]) -> Dict[str, int]:
        """Calculate total size per category.

        Args:
            categories: Dictionary of categorized file paths

        Returns:
            Dictionary mapping category names to total sizes in bytes
        """
        sizes: Dict[str, int] = {}

        for cat, files in categories.items():
            total = 0
            for file_path in files:
                try:
                    if file_path.exists():
                        total += file_path.stat().st_size
                except (OSError, PermissionError) as e:
                    logger.debug(f"Could not stat file {file_path}: {e}")
                    continue
            sizes[cat] = total

        return sizes

    def get_total_stats(
        self, categories: Dict[str, List[Path]]
    ) -> tuple[int, int]:
        """Get total file count and size for all categories.

        Args:
            categories: Dictionary of categorized file paths

        Returns:
            Tuple of (total_files, total_bytes)
        """
        total_files = sum(len(files) for files in categories.values())
        sizes = self.calculate_sizes(categories)
        total_bytes = sum(sizes.values())

        return total_files, total_bytes

    def analyze_single_file(self, file_path: Path) -> Dict[str, any]:
        """Analyze a single file and return metadata.

        Args:
            file_path: Path to file to analyze

        Returns:
            Dictionary with file metadata (size, category, exists, etc.)
        """
        result = {
            "path": file_path,
            "exists": file_path.exists(),
            "size": 0,
            "category": "unknown",
        }

        if not file_path.exists():
            return result

        try:
            result["size"] = file_path.stat().st_size

            # Determine category
            name_lower = file_path.name.lower()
            path_lower = str(file_path).lower()

            for category, patterns in self.CATEGORIES.items():
                for pattern in patterns:
                    if pattern in name_lower or pattern in path_lower:
                        result["category"] = category
                        return result

            result["category"] = "other"

        except (OSError, PermissionError) as e:
            logger.debug(f"Error analyzing file {file_path}: {e}")

        return result
