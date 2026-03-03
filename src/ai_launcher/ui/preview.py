"""Preview generation for ai-launcher."""

import subprocess  # nosec B404
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from ai_launcher.core.models import Project
from ai_launcher.utils.paths import is_relative_to

if TYPE_CHECKING:
    from ai_launcher.core.provider_data import DirectoryListing, GitStatus


def build_tree_view(
    projects: List[Project], base_path: Optional[Path] = None
) -> Tuple[List[str], Dict[str, Project]]:
    """Build a hierarchical tree view showing full folder structure.

    Format: Each line contains "absolute_path\t\ttree_display"
    fzf will be configured to only show tree_display but pass the whole line.

    Args:
        projects: List of projects to display
        base_path: Base path to use for relative display (optional)

    Returns:
        Tuple of (formatted_lines, line_to_project_mapping)
    """
    if not projects:
        return [], {}

    # Use provided base_path or calculate from projects
    if base_path:
        base = base_path
    else:
        # Find common base path
        if len(projects) == 1:
            base = projects[0].path.parent
        else:
            # Find common ancestor
            all_parts = [p.path.parts for p in projects]
            common_parts = []
            for parts in zip(*all_parts):
                if len(set(parts)) == 1:
                    common_parts.append(parts[0])
                else:
                    break

            # If we only have root as common, use the parent of the first project as base
            # This avoids showing the entire filesystem
            if not common_parts or (
                len(common_parts) == 1
                and Path(common_parts[0]).parent == Path(common_parts[0])
            ):
                # No meaningful common path - use first project's parent
                base = projects[0].path.parent
            else:
                base = Path(*common_parts)

    # Build full directory tree structure
    # Track all directories and their children (both dirs and projects)
    dir_children: Dict[Path, List[Path]] = {}  # dir -> child dirs
    dir_projects: Dict[Path, List[Project]] = {}  # dir -> projects in that dir

    # Collect all directories in the hierarchy
    all_dirs = set()
    for project in projects:
        # Add project to its parent directory
        parent = project.path.parent
        if parent not in dir_projects:
            dir_projects[parent] = []
        dir_projects[parent].append(project)

        # Add all ancestor directories
        current = project.path.parent
        while current != base and current != current.parent:
            all_dirs.add(current)
            parent_dir = current.parent
            if parent_dir != current and parent_dir != base.parent:
                if parent_dir not in dir_children:
                    dir_children[parent_dir] = []
                if current not in dir_children[parent_dir]:
                    dir_children[parent_dir].append(current)
            current = parent_dir

    # Sort children for consistent display
    for parent in dir_children:
        dir_children[parent].sort()

    formatted_lines = []
    line_to_project = {}

    def add_directory(
        dir_path: Path, prefix: str = "", is_last: bool = True, depth: int = 0
    ) -> None:
        """Recursively add directory tree."""
        # Show directory header if not the base
        if dir_path != base:
            connector = "└── " if is_last else "├── "
            # Get relative path from base for folder display
            try:
                rel_dir = dir_path.relative_to(base)
                dir_name = str(rel_dir)
            except ValueError:
                # Can't make relative - show full path
                dir_name = str(dir_path)

            dir_display = f"\033[2m{prefix}{connector}📁 {dir_name}/\033[0m"
            formatted_lines.append(f"{dir_path}\t\t{dir_display}")

            # Update prefix for children
            if is_last:
                child_prefix = prefix + "    "
            else:
                child_prefix = prefix + "│   "
        else:
            # Base directory - only show if it's meaningful (not root)
            if base.parent != base:
                # Format base path with ~ shorthand
                home = Path.home()
                display_base = (
                    f"~/{base.relative_to(home)}"
                    if is_relative_to(base, home)
                    else str(base)
                )
                dir_display = f"\033[2m📁 {display_base}/\033[0m"
                formatted_lines.append(f"{base}\t\t{dir_display}")
            child_prefix = ""

        # Get subdirectories and projects
        subdirs = dir_children.get(dir_path, [])
        projects_here = dir_projects.get(dir_path, [])

        # Sort projects
        projects_here = sorted(projects_here, key=lambda p: p.path.name)

        # Calculate total items (subdirs + projects)
        total_items = len(subdirs) + len(projects_here)
        item_idx = 0

        # Add subdirectories first
        for subdir in subdirs:
            item_idx += 1
            is_last_item = item_idx == total_items
            add_directory(subdir, child_prefix, is_last_item, depth + 1)

        # Add projects
        for project in projects_here:
            item_idx += 1
            is_last_item = item_idx == total_items

            connector = "└── " if is_last_item else "├── "

            # Format markers
            markers = []
            if project.is_git_repo:
                markers.append("git")
            if project.is_manual:
                markers.append("manual")
            marker_str = f" [{','.join(markers)}]" if markers else ""

            # Just show project name with visual hierarchy
            tree_display = f"{child_prefix}{connector}{project.path.name}{marker_str}"
            full_line = f"{project.path}\t\t{tree_display}"
            formatted_lines.append(full_line)
            line_to_project[full_line] = project

    # Start with base directory
    add_directory(base, "", True, 0)

    # Add manual projects that are outside the base path as a separate section
    external_manual_projects = []
    for project in projects:
        if project.is_manual:
            try:
                # Check if project is outside the base path
                project.path.relative_to(base)
            except ValueError:
                # Project is outside base path
                external_manual_projects.append(project)

    if external_manual_projects:
        # Add spacing line
        formatted_lines.append("__SPACE__\t\t")

        # Add header for external manual projects
        formatted_lines.append("__SPACE__\t\t📌 Manual Projects")

        # Add each external manual project (format like regular projects)
        for project in sorted(external_manual_projects, key=lambda p: str(p.path)):
            # Only show [git] marker if it's a git repo (like regular projects)
            marker_str = " [git]" if project.is_git_repo else ""

            # Just show project name with git marker (path shows in preview pane)
            tree_display = f"  {project.name}{marker_str}"
            full_line = f"{project.path}\t\t{tree_display}"
            formatted_lines.append(full_line)
            line_to_project[full_line] = project

    return formatted_lines, line_to_project


def _get_git_status(project_path: Path) -> Optional["GitStatus"]:
    """Get git status for a project (generic, not provider-specific).

    Args:
        project_path: Path to the project

    Returns:
        GitStatus instance or None if not a git repo
    """
    from ai_launcher.core.provider_data import GitStatus

    git_dir = project_path / ".git"
    if not git_dir.exists():
        return None

    try:
        # Get branch name
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=2,
        )  # nosec B603, B607
        branch = result.stdout.strip() if result.returncode == 0 else None

        # Get status
        result = subprocess.run(
            ["git", "status", "-s"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=2,
        )  # nosec B603, B607

        if result.returncode == 0:
            changed_files = [
                line.strip()
                for line in result.stdout.strip().split("\n")
                if line.strip()
            ]
            return GitStatus(
                is_repo=True,
                is_clean=len(changed_files) == 0,
                changed_files=changed_files,  # Show all changed files
                branch=branch,
                has_changes=len(changed_files) > 0,
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return GitStatus(is_repo=True)


def _get_directory_listing(project_path: Path) -> "DirectoryListing":
    """Get directory contents (generic, not provider-specific).

    Args:
        project_path: Path to the project

    Returns:
        DirectoryListing instance
    """
    from ai_launcher.core.provider_data import DirectoryListing

    try:
        directories = []
        files = []

        for item in project_path.iterdir():
            if item.is_dir():
                directories.append(item.name)
            else:
                files.append(item.name)

        return DirectoryListing(
            directories=sorted(directories),
            files=sorted(files),
            total_items=len(directories) + len(files),
        )
    except (PermissionError, OSError):
        return DirectoryListing()


def generate_provider_preview(
    project_path: Path, provider_name: str = "claude-code"
) -> str:
    """Generate preview using provider abstraction and formatter.

    Collects generic data (git, directory) and provider-specific data,
    then formats everything for display.

    Args:
        project_path: Path to the project
        provider_name: Name of provider to use (default: "claude-code")

    Returns:
        Formatted preview string ready for display
    """
    from ai_launcher.providers.registry import ProviderRegistry
    from ai_launcher.ui.formatter import PreviewFormatter

    # Get provider instance
    registry = ProviderRegistry()
    provider = registry.get(provider_name)

    if not provider:
        return f"⚠️  Provider '{provider_name}' not found"

    # 1. Collect GENERIC project data (same for all providers)
    git_status = _get_git_status(project_path)
    directory = _get_directory_listing(project_path)

    # 2. Collect PROVIDER-SPECIFIC data (includes session_config)
    try:
        provider_data = provider.collect_preview_data(project_path)
    except Exception as e:
        return f"⚠️  Error collecting preview data: {e}"

    # 3. Format ALL data (generic + provider-specific) for display
    formatter = PreviewFormatter()

    try:
        return formatter.format_complete_preview(
            project_path=project_path,
            provider_data=provider_data,
            git_status=git_status,
            directory=directory,
            session_config=provider_data.session_config,
        )
    except Exception as e:
        return f"⚠️  Error formatting preview: {e}"
