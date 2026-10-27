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
    seen_paths: set = set()
    # Track visited real directories to prevent cycles when following symlinks
    seen_real_dirs: set = set()

    for base_path in scan_paths:
        if not base_path.exists() or not base_path.is_dir():
            continue

        base_str = str(base_path)

        # followlinks=True so NTFS junctions and symlinks are traversed.
        # Python 3.12+ treats junctions as symlinks, so followlinks=False
        # silently skips them.  Cycle protection via seen_real_dirs and
        # max_depth keeps this safe.
        for root, dirs, files in os.walk(base_path, followlinks=True):
            # Cycle detection: skip directories we've already visited
            real_root = os.path.realpath(root)
            if real_root in seen_real_dirs:
                dirs[:] = []
                continue
            seen_real_dirs.add(real_root)

            # Calculate current depth
            depth = root[len(base_str) :].count(os.sep)

            if depth > max_depth:
                dirs[:] = []  # Stop deeper traversal
                continue

            # Check for .git before pruning (it's both in dirs and prune_dirs).
            # .git can be a directory (normal repos) or a file (submodules).
            has_git = ".git" in dirs or ".git" in files

            # Remove pruned directories from traversal. Name order, real folders
            # before symlinks: the result must not depend on the order the
            # filesystem lists names, and a real folder should win over a link
            # to it in the same parent (the cycle check keeps the first route).
            dirs[:] = sorted(
                (d for d in dirs if d not in prune_dirs),
                key=lambda d: ((Path(root) / d).is_symlink(), d),
            )

            if has_git:
                # The path as listed (symlinks are preserved); duplicates are
                # found by real path so a project reachable twice appears once.
                project_path = Path(root)

                if real_root not in seen_paths:
                    seen_paths.add(real_root)
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

    # Remove duplicates by real path (prefer manual over discovered). The path
    # each project keeps is the one as listed: symlinks are preserved.
    seen_paths = set()
    unique_projects = []

    # Process manual first (they take precedence)
    for project in sorted(manual_projects, key=lambda p: str(p.path)):
        real = os.path.realpath(project.path)
        if real not in seen_paths:
            seen_paths.add(real)
            unique_projects.append(project)

    # Then add discovered projects
    for project in discovered:
        real = os.path.realpath(project.path)
        if real not in seen_paths:
            seen_paths.add(real)
            unique_projects.append(project)

    # Sort alphabetically by path
    return sorted(unique_projects, key=lambda p: str(p.path))
