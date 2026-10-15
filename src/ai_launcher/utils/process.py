"""Process helpers.

Author: Solent Labs™
"""

import os
import sys


def pid_alive(pid: int) -> bool:
    """Is a process with this id running.

    Never uses os.kill on Windows: there, any signal but Ctrl-C and Ctrl-Break
    terminates the process, so signal 0 would kill it.
    """
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # it exists; it is another user's
    except OSError:
        return False
    return True


def _pid_alive_windows(pid: int) -> bool:  # pragma: no cover - Windows only
    """Ask Windows whether the process has exited, without signalling it."""
    import ctypes
    from ctypes import wintypes

    process_query_limited = 0x1000
    still_active = 259
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(process_query_limited, False, pid)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)
