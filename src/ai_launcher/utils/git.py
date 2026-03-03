"""Git utilities for ai-launcher."""

import subprocess  # nosec B404
from pathlib import Path
from typing import Optional


def clone_repository(
    url: str,
    target_base: Path,
    subfolder: Optional[str] = None,
) -> Path:
    """Clone a git repository.

    Args:
        url: Git repository URL (https or ssh)
        target_base: Base directory for cloning
        subfolder: Optional subfolder within target_base

    Returns:
        Path to cloned repository

    Raises:
        ValueError: If URL is invalid or target exists
        RuntimeError: If git clone fails
    """
    # Validate URL format
    if not (url.startswith("https://") or url.startswith("git@")):
        raise ValueError(
            f"Invalid git URL: {url}\nMust start with 'https://' or 'git@'"
        )

    # Extract repository name from URL
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")

    # Construct target path
    if subfolder:
        target_path = target_base / subfolder / repo_name
    else:
        target_path = target_base / repo_name

    # Check if target already exists
    if target_path.exists():
        raise ValueError(f"Directory already exists: {target_path}")

    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Clone repository
    try:
        print(f"Cloning {url}...")
        print(f"Target: {target_path}\n")

        subprocess.run(  # nosec B603, B607
            ["git", "clone", url, str(target_path)],
            capture_output=True,
            text=True,
            check=True,
        )

        print("Clone successful!")
        return target_path

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        raise RuntimeError(f"Git clone failed: {error_msg}")
    except FileNotFoundError:
        raise RuntimeError("Git command not found. Please install git.")
