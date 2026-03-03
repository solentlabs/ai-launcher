"""Tests for fzf detection and auto-download utility."""

import io
import json
import os
import stat
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_launcher.utils.fzf import (
    _add_to_path,
    _get_platform_info,
    _print_manual_instructions,
    download_fzf,
    ensure_fzf,
    get_fzf_download_url,
    get_fzf_install_dir,
    is_fzf_installed,
)

# ---------------------------------------------------------------------------
# is_fzf_installed
# ---------------------------------------------------------------------------


class TestIsFzfInstalled:
    def test_returns_true_when_fzf_on_path(self):
        with patch("ai_launcher.utils.fzf.shutil.which", return_value="/usr/bin/fzf"):
            assert is_fzf_installed() is True

    def test_returns_false_when_fzf_missing(self):
        with patch("ai_launcher.utils.fzf.shutil.which", return_value=None):
            assert is_fzf_installed() is False


# ---------------------------------------------------------------------------
# get_fzf_install_dir
# ---------------------------------------------------------------------------


class TestGetFzfInstallDir:
    def test_returns_path_with_bin_suffix(self):
        result = get_fzf_install_dir()
        assert result.name == "bin"
        assert "ai-launcher" in str(result)

    def test_returns_path_object(self):
        result = get_fzf_install_dir()
        assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# _get_platform_info
# ---------------------------------------------------------------------------


class TestGetPlatformInfo:
    @pytest.mark.parametrize(
        "system, machine, expected_os, expected_arch",
        [
            ("Linux", "x86_64", "linux", "amd64"),
            ("Linux", "aarch64", "linux", "arm64"),
            ("Linux", "amd64", "linux", "amd64"),
            ("Linux", "arm64", "linux", "arm64"),
            ("Darwin", "x86_64", "darwin", "amd64"),
            ("Darwin", "arm64", "darwin", "arm64"),
            ("Windows", "AMD64", "windows", "amd64"),
        ],
    )
    def test_supported_platforms(self, system, machine, expected_os, expected_arch):
        with patch("ai_launcher.utils.fzf.platform.system", return_value=system):
            with patch("ai_launcher.utils.fzf.platform.machine", return_value=machine):
                os_name, arch = _get_platform_info()
                assert os_name == expected_os
                assert arch == expected_arch

    def test_unsupported_os_raises(self):
        with patch("ai_launcher.utils.fzf.platform.system", return_value="FreeBSD"):
            with patch("ai_launcher.utils.fzf.platform.machine", return_value="x86_64"):
                with pytest.raises(RuntimeError, match="Unsupported operating system"):
                    _get_platform_info()

    def test_unsupported_arch_raises(self):
        with patch("ai_launcher.utils.fzf.platform.system", return_value="Linux"):
            with patch("ai_launcher.utils.fzf.platform.machine", return_value="mips"):
                with pytest.raises(RuntimeError, match="Unsupported architecture"):
                    _get_platform_info()


# ---------------------------------------------------------------------------
# get_fzf_download_url
# ---------------------------------------------------------------------------


def _make_github_response(assets):
    """Helper to create a mock GitHub API response."""
    data = json.dumps({"assets": assets}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = data
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestGetFzfDownloadUrl:
    def test_linux_amd64(self):
        assets = [
            {
                "name": "fzf-0.60.3-linux_amd64.tar.gz",
                "browser_download_url": "https://github.com/junegunn/fzf/releases/download/v0.60.3/fzf-0.60.3-linux_amd64.tar.gz",
            },
            {
                "name": "fzf-0.60.3-darwin_arm64.tar.gz",
                "browser_download_url": "https://example.com/darwin",
            },
        ]
        mock_resp = _make_github_response(assets)

        with patch(
            "ai_launcher.utils.fzf._get_platform_info", return_value=("linux", "amd64")
        ):
            with patch("ai_launcher.utils.fzf.urlopen", return_value=mock_resp):
                url = get_fzf_download_url()
                assert "linux_amd64" in url
                assert url.endswith(".tar.gz")

    def test_darwin_arm64(self):
        assets = [
            {
                "name": "fzf-0.60.3-darwin_arm64.tar.gz",
                "browser_download_url": "https://github.com/junegunn/fzf/releases/download/v0.60.3/fzf-0.60.3-darwin_arm64.tar.gz",
            },
        ]
        mock_resp = _make_github_response(assets)

        with patch(
            "ai_launcher.utils.fzf._get_platform_info", return_value=("darwin", "arm64")
        ):
            with patch("ai_launcher.utils.fzf.urlopen", return_value=mock_resp):
                url = get_fzf_download_url()
                assert "darwin_arm64" in url

    def test_windows_amd64(self):
        assets = [
            {
                "name": "fzf-0.60.3-windows_amd64.zip",
                "browser_download_url": "https://github.com/junegunn/fzf/releases/download/v0.60.3/fzf-0.60.3-windows_amd64.zip",
            },
        ]
        mock_resp = _make_github_response(assets)

        with patch(
            "ai_launcher.utils.fzf._get_platform_info",
            return_value=("windows", "amd64"),
        ):
            with patch("ai_launcher.utils.fzf.urlopen", return_value=mock_resp):
                url = get_fzf_download_url()
                assert "windows_amd64" in url
                assert url.endswith(".zip")

    def test_exact_name_match(self):
        """Test matching the exact asset name (no version prefix)."""
        assets = [
            {
                "name": "fzf-linux_amd64.tar.gz",
                "browser_download_url": "https://example.com/fzf-linux_amd64.tar.gz",
            },
        ]
        mock_resp = _make_github_response(assets)

        with patch(
            "ai_launcher.utils.fzf._get_platform_info", return_value=("linux", "amd64")
        ):
            with patch("ai_launcher.utils.fzf.urlopen", return_value=mock_resp):
                url = get_fzf_download_url()
                assert url == "https://example.com/fzf-linux_amd64.tar.gz"

    def test_no_matching_asset_raises(self):
        assets = [
            {
                "name": "fzf-freebsd_amd64.tar.gz",
                "browser_download_url": "https://example.com/freebsd",
            },
        ]
        mock_resp = _make_github_response(assets)

        with patch(
            "ai_launcher.utils.fzf._get_platform_info", return_value=("linux", "amd64")
        ):
            with patch("ai_launcher.utils.fzf.urlopen", return_value=mock_resp):
                with pytest.raises(RuntimeError, match="No fzf release found"):
                    get_fzf_download_url()

    def test_github_api_failure_raises(self):
        from urllib.error import URLError

        with patch(
            "ai_launcher.utils.fzf._get_platform_info", return_value=("linux", "amd64")
        ):
            with patch(
                "ai_launcher.utils.fzf.urlopen",
                side_effect=URLError("connection refused"),
            ):
                with pytest.raises(RuntimeError, match="Failed to query GitHub API"):
                    get_fzf_download_url()


# ---------------------------------------------------------------------------
# download_fzf
# ---------------------------------------------------------------------------


def _make_tar_archive(binary_name="fzf"):
    """Create a tar.gz archive containing a fake fzf binary."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        data = b"#!/bin/sh\necho fzf"
        info = tarfile.TarInfo(name=binary_name)
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _make_zip_archive(binary_name="fzf.exe"):
    """Create a zip archive containing a fake fzf binary."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(binary_name, b"fake fzf binary")
    return buf.getvalue()


class TestDownloadFzf:
    def test_download_tar_gz(self, tmp_path):
        archive_data = _make_tar_archive("fzf")
        mock_resp = MagicMock()
        mock_resp.read.return_value = archive_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        install_dir = tmp_path / "bin"

        with patch(
            "ai_launcher.utils.fzf.get_fzf_download_url",
            return_value="https://example.com/fzf-linux_amd64.tar.gz",
        ):
            with patch("ai_launcher.utils.fzf.urlopen", return_value=mock_resp):
                with patch(
                    "ai_launcher.utils.fzf.platform.system", return_value="Linux"
                ):
                    result = download_fzf(install_dir)

        assert result == install_dir / "fzf"
        assert result.exists()
        # Verify executable bit is set (only meaningful on Unix filesystems)
        if os.name != "nt":
            assert result.stat().st_mode & stat.S_IXUSR

    def test_download_zip(self, tmp_path):
        archive_data = _make_zip_archive("fzf.exe")
        mock_resp = MagicMock()
        mock_resp.read.return_value = archive_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        install_dir = tmp_path / "bin"

        with patch(
            "ai_launcher.utils.fzf.get_fzf_download_url",
            return_value="https://example.com/fzf-windows_amd64.zip",
        ):
            with patch("ai_launcher.utils.fzf.urlopen", return_value=mock_resp):
                with patch(
                    "ai_launcher.utils.fzf.platform.system", return_value="Windows"
                ):
                    result = download_fzf(install_dir)

        assert result == install_dir / "fzf.exe"
        assert result.exists()

    def test_download_creates_install_dir(self, tmp_path):
        archive_data = _make_tar_archive("fzf")
        mock_resp = MagicMock()
        mock_resp.read.return_value = archive_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        install_dir = tmp_path / "nested" / "deep" / "bin"
        assert not install_dir.exists()

        with patch(
            "ai_launcher.utils.fzf.get_fzf_download_url",
            return_value="https://example.com/fzf-linux_amd64.tar.gz",
        ):
            with patch("ai_launcher.utils.fzf.urlopen", return_value=mock_resp):
                with patch(
                    "ai_launcher.utils.fzf.platform.system", return_value="Linux"
                ):
                    download_fzf(install_dir)

        assert install_dir.exists()

    def test_download_failure_raises(self, tmp_path):
        from urllib.error import URLError

        with patch(
            "ai_launcher.utils.fzf.get_fzf_download_url",
            return_value="https://example.com/fzf-linux_amd64.tar.gz",
        ):
            with patch(
                "ai_launcher.utils.fzf.urlopen",
                side_effect=URLError("timeout"),
            ):
                with patch(
                    "ai_launcher.utils.fzf.platform.system", return_value="Linux"
                ):
                    with pytest.raises(RuntimeError, match="Failed to download fzf"):
                        download_fzf(tmp_path / "bin")

    def test_missing_binary_in_archive_raises(self, tmp_path):
        """Archive that doesn't contain the expected binary name."""
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            data = b"not fzf"
            info = tarfile.TarInfo(name="README.md")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        archive_data = buf.getvalue()

        mock_resp = MagicMock()
        mock_resp.read.return_value = archive_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch(
            "ai_launcher.utils.fzf.get_fzf_download_url",
            return_value="https://example.com/fzf-linux_amd64.tar.gz",
        ):
            with patch("ai_launcher.utils.fzf.urlopen", return_value=mock_resp):
                with patch(
                    "ai_launcher.utils.fzf.platform.system", return_value="Linux"
                ):
                    with pytest.raises(
                        RuntimeError, match="'fzf' not found in archive"
                    ):
                        download_fzf(tmp_path / "bin")


# ---------------------------------------------------------------------------
# _add_to_path
# ---------------------------------------------------------------------------


class TestAddToPath:
    def test_adds_directory_to_path(self, tmp_path):
        original_path = os.environ.get("PATH", "")
        try:
            _add_to_path(tmp_path)
            assert str(tmp_path) in os.environ["PATH"]
        finally:
            os.environ["PATH"] = original_path

    def test_does_not_duplicate(self, tmp_path):
        original_path = os.environ.get("PATH", "")
        try:
            _add_to_path(tmp_path)
            path_after_first = os.environ["PATH"]
            _add_to_path(tmp_path)
            assert os.environ["PATH"] == path_after_first
        finally:
            os.environ["PATH"] = original_path

    def test_prepends_to_path(self, tmp_path):
        original_path = os.environ.get("PATH", "")
        try:
            _add_to_path(tmp_path)
            assert os.environ["PATH"].startswith(str(tmp_path))
        finally:
            os.environ["PATH"] = original_path


# ---------------------------------------------------------------------------
# _print_manual_instructions
# ---------------------------------------------------------------------------


class TestPrintManualInstructions:
    def test_linux_instructions(self, capsys):
        with patch("ai_launcher.utils.fzf.platform.system", return_value="Linux"):
            _print_manual_instructions()
        output = capsys.readouterr().out
        assert "apt install fzf" in output

    def test_darwin_instructions(self, capsys):
        with patch("ai_launcher.utils.fzf.platform.system", return_value="Darwin"):
            _print_manual_instructions()
        output = capsys.readouterr().out
        assert "brew install fzf" in output

    def test_windows_instructions(self, capsys):
        with patch("ai_launcher.utils.fzf.platform.system", return_value="Windows"):
            _print_manual_instructions()
        output = capsys.readouterr().out
        assert "winget install" in output
        assert "scoop install fzf" in output

    def test_unknown_os_instructions(self, capsys):
        with patch("ai_launcher.utils.fzf.platform.system", return_value="Haiku"):
            _print_manual_instructions()
        output = capsys.readouterr().out
        assert "github.com/junegunn/fzf" in output


# ---------------------------------------------------------------------------
# ensure_fzf
# ---------------------------------------------------------------------------


class TestEnsureFzf:
    def test_already_installed_returns_true(self):
        with patch("ai_launcher.utils.fzf.is_fzf_installed", return_value=True):
            assert ensure_fzf() is True

    def test_found_in_install_dir(self, tmp_path):
        """fzf previously downloaded to our install dir."""
        install_dir = tmp_path / "bin"
        install_dir.mkdir(parents=True)
        fzf_binary = install_dir / "fzf"
        fzf_binary.write_text("#!/bin/sh\necho fzf")
        fzf_binary.chmod(0o755)

        call_count = 0

        def mock_is_installed():
            nonlocal call_count
            call_count += 1
            # First call: not on system PATH; second call: found after adding to PATH
            return call_count > 1

        with patch(
            "ai_launcher.utils.fzf.is_fzf_installed", side_effect=mock_is_installed
        ):
            with patch(
                "ai_launcher.utils.fzf.get_fzf_install_dir", return_value=install_dir
            ):
                with patch(
                    "ai_launcher.utils.fzf.platform.system", return_value="Linux"
                ):
                    assert ensure_fzf() is True

    def test_user_accepts_download(self, tmp_path):
        install_dir = tmp_path / "bin"

        call_count = 0

        def mock_is_installed():
            nonlocal call_count
            call_count += 1
            # First call: not on PATH; second call (after download): found
            return call_count > 1

        with patch(
            "ai_launcher.utils.fzf.is_fzf_installed", side_effect=mock_is_installed
        ):
            with patch(
                "ai_launcher.utils.fzf.get_fzf_install_dir", return_value=install_dir
            ):
                with patch(
                    "ai_launcher.utils.fzf.platform.system", return_value="Linux"
                ):
                    with patch("builtins.input", return_value="y"):
                        with patch(
                            "ai_launcher.utils.fzf.download_fzf",
                            return_value=install_dir / "fzf",
                        ):
                            assert ensure_fzf() is True

    def test_user_accepts_with_empty_input(self, tmp_path):
        """Empty input (just Enter) defaults to yes."""
        install_dir = tmp_path / "bin"

        call_count = 0

        def mock_is_installed():
            nonlocal call_count
            call_count += 1
            return call_count > 1

        with patch(
            "ai_launcher.utils.fzf.is_fzf_installed", side_effect=mock_is_installed
        ):
            with patch(
                "ai_launcher.utils.fzf.get_fzf_install_dir", return_value=install_dir
            ):
                with patch(
                    "ai_launcher.utils.fzf.platform.system", return_value="Linux"
                ):
                    with patch("builtins.input", return_value=""):
                        with patch(
                            "ai_launcher.utils.fzf.download_fzf",
                            return_value=install_dir / "fzf",
                        ):
                            assert ensure_fzf() is True

    def test_user_declines_download(self, tmp_path, capsys):
        install_dir = tmp_path / "bin"

        with patch("ai_launcher.utils.fzf.is_fzf_installed", return_value=False):
            with patch(
                "ai_launcher.utils.fzf.get_fzf_install_dir", return_value=install_dir
            ):
                with patch(
                    "ai_launcher.utils.fzf.platform.system", return_value="Linux"
                ):
                    with patch("builtins.input", return_value="n"):
                        assert ensure_fzf() is False

        output = capsys.readouterr().out
        assert "install fzf manually" in output.lower() or "apt install fzf" in output

    def test_download_error_shows_manual_instructions(self, tmp_path, capsys):
        install_dir = tmp_path / "bin"

        with patch("ai_launcher.utils.fzf.is_fzf_installed", return_value=False):
            with patch(
                "ai_launcher.utils.fzf.get_fzf_install_dir", return_value=install_dir
            ):
                with patch(
                    "ai_launcher.utils.fzf.platform.system", return_value="Linux"
                ):
                    with patch("builtins.input", return_value="y"):
                        with patch(
                            "ai_launcher.utils.fzf.download_fzf",
                            side_effect=RuntimeError("Network error"),
                        ):
                            assert ensure_fzf() is False

        output = capsys.readouterr().out
        assert "Network error" in output
        assert "apt install fzf" in output

    def test_eof_on_input_returns_false(self, tmp_path):
        install_dir = tmp_path / "bin"

        with patch("ai_launcher.utils.fzf.is_fzf_installed", return_value=False):
            with patch(
                "ai_launcher.utils.fzf.get_fzf_install_dir", return_value=install_dir
            ):
                with patch(
                    "ai_launcher.utils.fzf.platform.system", return_value="Linux"
                ):
                    with patch("builtins.input", side_effect=EOFError):
                        assert ensure_fzf() is False

    def test_keyboard_interrupt_returns_false(self, tmp_path):
        install_dir = tmp_path / "bin"

        with patch("ai_launcher.utils.fzf.is_fzf_installed", return_value=False):
            with patch(
                "ai_launcher.utils.fzf.get_fzf_install_dir", return_value=install_dir
            ):
                with patch(
                    "ai_launcher.utils.fzf.platform.system", return_value="Linux"
                ):
                    with patch("builtins.input", side_effect=KeyboardInterrupt):
                        assert ensure_fzf() is False

    def test_path_updated_after_download(self, tmp_path):
        """Verify PATH is updated after successful download."""
        install_dir = tmp_path / "bin"
        original_path = os.environ.get("PATH", "")

        call_count = 0

        def mock_is_installed():
            nonlocal call_count
            call_count += 1
            return call_count > 1

        try:
            with patch(
                "ai_launcher.utils.fzf.is_fzf_installed", side_effect=mock_is_installed
            ):
                with patch(
                    "ai_launcher.utils.fzf.get_fzf_install_dir",
                    return_value=install_dir,
                ):
                    with patch(
                        "ai_launcher.utils.fzf.platform.system", return_value="Linux"
                    ):
                        with patch("builtins.input", return_value="y"):
                            with patch(
                                "ai_launcher.utils.fzf.download_fzf",
                                return_value=install_dir / "fzf",
                            ):
                                ensure_fzf()

            assert str(install_dir) in os.environ["PATH"]
        finally:
            os.environ["PATH"] = original_path
