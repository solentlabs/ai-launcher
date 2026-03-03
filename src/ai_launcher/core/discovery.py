"""Project discovery for ai-launcher."""

import os
from pathlib import Path
from typing import List

from ai_launcher.core.models import Project


def scan_for_git_repos(
    scan_paths: List[Path],
    max_depth: int,
    prune_dirs: List[str],
) -> List[Project]:
    """Recursively scan directories for git repositories.

    Args:
        scan_paths: List of base directories to scan
        max_depth: Maximum depth to traverse
        prune_dirs: Directory names to skip during traversal

    Returns:
        List of discovered Project instances
    """
    projects = []
    seen_paths = set()

    for base_path in scan_paths:
        if not base_path.exists() or not base_path.is_dir():
            continue

        base_str = str(base_path.resolve())

        for root, dirs, _ in os.walk(base_path, followlinks=False):
            # Calculate current depth
            depth = root[len(base_str) :].count(os.sep)

            if depth > max_depth:
                dirs[:] = []  # Stop deeper traversal
                continue

            # Remove pruned directories from traversal
            dirs[:] = [d for d in dirs if d not in prune_dirs]

            # Check if this is a git repository
            if ".git" in os.listdir(root):
                project_path = Path(root).resolve()
                path_str = str(project_path)

                # Avoid duplicates
                if path_str not in seen_paths:
                    seen_paths.add(path_str)
                    projects.append(Project.from_path(project_path, is_manual=False))

    return projects


def get_all_projects(
    scan_paths: List[Path],
    max_depth: int,
    prune_dirs: List[str],
    manual_projects: List[Project],
) -> List[Project]:
    """Get all projects (discovered + manual), sorted alphabetically.

    Args:
        scan_paths: Directories to scan for git repos
        max_depth: Maximum scan depth
        prune_dirs: Directories to skip
        manual_projects: Manually added projects

    Returns:
        Sorted list of all unique projects
    """
    # Scan for git repositories
    discovered = scan_for_git_repos(scan_paths, max_depth, prune_dirs)

    # Remove duplicates (prefer manual over discovered)
    seen_paths = set()
    unique_projects = []

    # Process manual first (they take precedence)
    for project in sorted(manual_projects, key=lambda p: str(p.path)):
        path_str = str(project.path)
        if path_str not in seen_paths:
            seen_paths.add(path_str)
            unique_projects.append(project)

    # Then add discovered projects
    for project in discovered:
        path_str = str(project.path)
        if path_str not in seen_paths:
            seen_paths.add(path_str)
            unique_projects.append(project)

    # Sort alphabetically by path
    return sorted(unique_projects, key=lambda p: str(p.path))
