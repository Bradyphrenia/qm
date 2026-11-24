"""Windows-only named mutex used by the app and its updater."""
from __future__ import annotations

import ctypes
import sys


APP_MUTEX_NAME = r"Local\QMDesktop-Application"
ERROR_ALREADY_EXISTS = 183


class ApplicationInstance:
    """Own a Windows mutex handle for the lifetime of this object."""

    def __init__(self, handle=None):
        self._handle = handle

    def close(self):
        if self._handle is not None:
            try:
                kernel32 = ctypes.windll.kernel32
                kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
                kernel32.CloseHandle.restype = ctypes.c_bool
                kernel32.CloseHandle(self._handle)
            except (AttributeError, OSError):
                pass
            self._handle = None

    def __del__(self):
        self.close()


def acquire_application_instance():
    """Return a guard, or ``None`` when another Windows instance exists."""
    if sys.platform != "win32":
        return ApplicationInstance()
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_bool
    kernel32.GetLastError.restype = ctypes.c_ulong
    handle = kernel32.CreateMutexW(None, False, APP_MUTEX_NAME)
    if not handle:
        raise ctypes.WinError()
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return ApplicationInstance(handle)
