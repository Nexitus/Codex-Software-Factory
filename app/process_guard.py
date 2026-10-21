from __future__ import annotations

import sys
from pathlib import Path


def process_birth(pid: int) -> str | None:
    """Return an OS process creation marker that guards against PID reuse."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                             ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
                                             ctypes.POINTER(wintypes.FILETIME))
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            creation, exit_time, kernel, user = (wintypes.FILETIME() for _ in range(4))
            if not kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                            ctypes.byref(kernel), ctypes.byref(user)):
                return None
            value = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            return f"win:{value}"
        finally:
            kernel32.CloseHandle(handle)
    stat = Path(f"/proc/{pid}/stat")
    if stat.is_file():
        try:
            tail = stat.read_text(encoding="ascii").rsplit(") ", 1)[1].split()
            return f"proc:{tail[19]}"
        except (OSError, IndexError):
            return None
    return None


def process_matches(pid: int | None, token: str | None) -> bool:
    return bool(pid and token and process_birth(pid) == token)
