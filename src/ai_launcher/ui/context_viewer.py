"""Interactive context viewer UI for visualizing provider context.

Author: Solent Labs™
Created: 2026-02-09
"""

import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import List

from ai_launcher.core.models import Project, ProviderInfo
from ai_launcher.utils.logging import get_logger
from ai_launcher.utils.paths import fzf_preview_cmd

logger = get_logger(__name__)


def show_context_viewer(
    providers: List[ProviderInfo],
    projects: List[Project],
) -> None:
    """Show interactive context visualization using fzf.

    Displays a two-panel interface where users can browse providers and
    projects, with the preview pane showing detailed context information.

    Args:
        providers: List of detected providers
        projects: List of discovered projects
    """
    # Build fzf items
    items = []

    # Section: Providers
    items.append("__HEADER__\t\tPROVIDERS")
    for provider in providers:
        if provider.context:
            status = "✓"
            version_str = (
                f" v{provider.context.version}" if provider.context.version else ""
            )
            label = f"{provider.name}{version_str}"
        else:
            status = "✗"
            label = f"{provider.name} (not installed)"

        items.append(f"PROVIDER:{provider.name}\t\t  {status} {label}")

    items.append("__SPACER__\t\t")

    # Section: Projects
    items.append("__HEADER__\t\tPROJECTS")
    for project in projects[:20]:
        marker = "🔧" if project.is_git_repo else "📁"
        items.append(f"PROJECT:{project.path}\t\t  {marker} {project.name}")

    if len(projects) > 20:
        remaining = len(projects) - 20
        items.append(f"__INFO__\t\t  ... and {remaining} more projects")

    try:
        # Get path to preview helper script
        helper_script = Path(__file__).parent / "_context_preview.py"

        # Build preview command
        preview_cmd = fzf_preview_cmd(helper_script, "{}")

        # Run fzf
        fzf_cmd = [
            "fzf",
            "--prompt=Context > ",
            "--height=100%",
            "--layout=reverse",
            "--border=rounded",
            "--border-label= Context Visualization ",
            "--delimiter=\\t\\t",
            "--with-nth=2..",
            "--preview-window=right:60%:wrap:border-left",
            f"--preview={preview_cmd}",
            "--ansi",
            "--disabled",  # Disable search, just for browsing
        ]

        input_data = "\n".join(items)
        process = subprocess.Popen(  # nosec B603
            fzf_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        process.communicate(input=input_data.encode("utf-8"))

    except FileNotFoundError:
        print("Error: fzf not found. Please install fzf to use the context viewer.")
        print("Install: https://github.com/junegunn/fzf")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error running context viewer: {e}")
        print(f"Error: Could not launch context viewer: {e}")
        sys.exit(1)
