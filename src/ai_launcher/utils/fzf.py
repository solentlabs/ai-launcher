"""fzf detection and auto-download utility.

Detects whether fzf is installed, and if not, offers to download the binary
from GitHub releases automatically.

Author: Solent Labs™
"""

import os
import platform
import shutil
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

import platformdirs

# GitHub release URL pattern
_FZF_GITHUB_API = "https://api.github.com/repos/junegunn/fzf/releases/latest"


def is_fzf_installed() -> bool:
    """Check if fzf is available on PATH."""
    return shutil.which("fzf") is not None


def get_fzf_install_dir() -> Path:
    """Return the platform-appropriate directory for storing the fzf binary.

    - Linux: ~/.local/share/ai-launcher/bin/
    - macOS: ~/Library/Application Support/ai-launcher/bin/
    - Windows: %LOCALAPPDATA%\\ai-launcher\\bin\\
    """
    return Path(platformdirs.user_data_path("ai-launcher")) / "bin"


def _get_platform_info() -> Tuple[str, str]:
    """Return (os_name, arch) mapped to fzf release naming conventions."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Map OS
    if system == "linux":
        os_name = "linux"
    elif system == "darwin":
        os_name = "darwin"
    elif system == "windows":
        os_name = "windows"
    else:
        raise RuntimeError(f"Unsupported operating system: {system}")

    # Map architecture
    if machine in ("x86_64", "amd64"):
        arch = "amd64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        raise RuntimeError(f"Unsupported architecture: {machine}")

    return os_name, arch


def get_fzf_download_url() -> str:
    """Get the download URL for the latest fzf release for this platform.

    Queries the GitHub API to find the latest release, then selects the
    appropriate asset for the current OS and architecture.
    """
    os_name, arch = _get_platform_info()

    # Build the expected asset name pattern
    ext = "zip" if os_name == "windows" else "tar.gz"
    asset_pattern = f"fzf-{os_name}_{arch}.{ext}"

    # Minimal workaround: also match versioned filenames like
    # fzf-0.60.3-linux_amd64.tar.gz
    suffix_pattern = f"-{os_name}_{arch}.{ext}"

    req = Request(_FZF_GITHUB_API)  # noqa: S310
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "ai-launcher")

    try:
        with urlopen(req, timeout=15) as resp:  # noqa: S310
            import json

            data = json.loads(resp.read().decode())
    except (URLError, OSError) as e:
        raise RuntimeError(f"Failed to query GitHub API: {e}") from e

    # Find matching asset
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name == asset_pattern or name.endswith(suffix_pattern):
            url: str = asset["browser_download_url"]
            return url

    raise RuntimeError(
        f"No fzf release found for {os_name}/{arch}. "
        f"Expected asset matching: {asset_pattern}"
    )


def download_fzf(install_dir: Optional[Path] = None) -> Path:
    """Download and extract fzf to the specified directory.

    Args:
        install_dir: Target directory. Defaults to get_fzf_install_dir().

    Returns:
        Path to the installed fzf binary.
    """
    if install_dir is None:
        install_dir = get_fzf_install_dir()

    install_dir.mkdir(parents=True, exist_ok=True)

    url = get_fzf_download_url()
    is_zip = url.endswith(".zip")

    print("  Downloading fzf from GitHub...")

    req = Request(url)  # noqa: S310
    req.add_header("User-Agent", "ai-launcher")

    try:
        with urlopen(req, timeout=60) as resp:  # noqa: S310
            archive_data = resp.read()
    except (URLError, OSError) as e:
        raise RuntimeError(f"Failed to download fzf: {e}") from e

    # Extract the fzf binary
    binary_name = "fzf.exe" if platform.system().lower() == "windows" else "fzf"
    target_path = install_dir / binary_name

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        archive_path = tmppath / ("fzf.zip" if is_zip else "fzf.tar.gz")
        archive_path.write_bytes(archive_data)

        if is_zip:
            with zipfile.ZipFile(archive_path) as zf:
                # Find the fzf binary in the archive
                for name in zf.namelist():
                    if Path(name).name == binary_name:
                        zf.extract(name, tmpdir)
                        extracted = tmppath / name
                        shutil.move(str(extracted), str(target_path))
                        break
                else:
                    raise RuntimeError(f"'{binary_name}' not found in archive")
        else:
            with tarfile.open(archive_path, "r:gz") as tf:
                for member in tf.getmembers():
                    if Path(member.name).name == binary_name:
                        tf.extract(member, tmpdir)
                        extracted = tmppath / member.name
                        shutil.move(str(extracted), str(target_path))
                        break
                else:
                    raise RuntimeError(f"'{binary_name}' not found in archive")

    # Set executable permissions on Unix
    if platform.system().lower() != "windows":
        target_path.chmod(target_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)

    print(f"  Installed fzf to {target_path}")
    return target_path


def _add_to_path(directory: Path) -> None:
    """Add a directory to the current process PATH."""
    dir_str = str(directory)
    current_path = os.environ.get("PATH", "")
    if dir_str not in current_path.split(os.pathsep):
        os.environ["PATH"] = dir_str + os.pathsep + current_path


def _print_manual_instructions() -> None:
    """Print platform-specific manual install instructions for fzf."""
    system = platform.system().lower()

    print("\n  To install fzf manually:")
    if system == "linux":
        print("    sudo apt install fzf        # Debian/Ubuntu")
        print("    sudo dnf install fzf         # Fedora")
        print("    sudo pacman -S fzf           # Arch")
    elif system == "darwin":
        print("    brew install fzf")
    elif system == "windows":
        print("    winget install junegunn.fzf")
        print("    scoop install fzf")
        print("    choco install fzf")
    else:
        print("    See https://github.com/junegunn/fzf#installation")
    print()


def ensure_fzf() -> bool:
    """Ensure fzf is available, offering to download it if missing.

    Returns True if fzf is available (either already installed or
    successfully downloaded). Returns False if fzf is unavailable
    and the user declined to download it.
    """
    # 1. Check system PATH
    if is_fzf_installed():
        return True

    # 2. Check our own install directory (from a previous download)
    install_dir = get_fzf_install_dir()
    binary_name = "fzf.exe" if platform.system().lower() == "windows" else "fzf"
    local_fzf = install_dir / binary_name

    if local_fzf.exists():
        _add_to_path(install_dir)
        if is_fzf_installed():
            return True

    # 3. fzf is not found — prompt user
    print("\n  fzf is required but not found on your system.")
    print("  fzf powers the interactive project selector.\n")

    try:
        response = input("  Download fzf automatically? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False

    if response in ("", "y", "yes"):
        try:
            download_fzf(install_dir)
            _add_to_path(install_dir)
            if is_fzf_installed():
                return True
            print("  Error: fzf was downloaded but could not be found on PATH.")
            return False
        except RuntimeError as e:
            print(f"  Error: {e}")
            _print_manual_instructions()
            return False
    else:
        _print_manual_instructions()
        return False
