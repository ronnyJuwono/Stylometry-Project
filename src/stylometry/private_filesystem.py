"""Internal no-link file reader. Never call directly from UI/application code.

Windows keeps all ancestor handles open without write/delete sharing during a
read. POSIX walks directory descriptors with O_NOFOLLOW. No directory scanning,
file creation, database operations or physical path logging occurs here.
"""

from contextlib import ExitStack
import os
from pathlib import Path
import re
import stat


def read_private_file(root: Path, parts: tuple[str, ...], limit: int) -> bytes:
    if (not root.is_absolute() or ".." in root.parts or not parts
            or any(part in (".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts)):
        raise OSError("Unsafe private location")
    if os.name == "nt":
        return _read_windows(root, parts, limit)
    if os.name == "posix" and os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
        return _read_posix(root, parts, limit)
    raise OSError("Unsupported private filesystem")


def _read_posix(root: Path, parts: tuple[str, ...], limit: int) -> bytes:
    with ExitStack() as handles:
        def open_at(name, flags, parent=None):
            fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            handles.callback(os.close, fd)
            return fd

        directory = open_at(root.anchor, os.O_RDONLY | os.O_DIRECTORY)
        for part in (*root.parts[1:], *parts[:-1]):
            directory = open_at(part, os.O_RDONLY | os.O_DIRECTORY, directory)
        fd = open_at(parts[-1], os.O_RDONLY, directory)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise OSError("Unsafe private file")
        chunks, size = [], 0
        while chunk := os.read(fd, min(65536, limit - size + 1)):
            size += len(chunk)
            if size > limit:
                raise OSError("Private file exceeds limit")
            chunks.append(chunk)
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise OSError("Private file changed")
        return b"".join(chunks)


def _read_windows(root: Path, parts: tuple[str, ...], limit: int) -> bytes:
    import ctypes
    from ctypes import wintypes as w

    class Information(ctypes.Structure):
        _fields_ = [("attributes", w.DWORD), ("created", w.FILETIME),
                    ("accessed", w.FILETIME), ("written", w.FILETIME),
                    ("volume", w.DWORD), ("size_high", w.DWORD), ("size_low", w.DWORD),
                    ("links", w.DWORD), ("index_high", w.DWORD), ("index_low", w.DWORD)]

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
    api.CreateFileW.restype = w.HANDLE
    api.CloseHandle.argtypes = [w.HANDLE]
    api.CloseHandle.restype = w.BOOL
    api.GetFileInformationByHandle.argtypes = [w.HANDLE, ctypes.POINTER(Information)]
    api.GetFileInformationByHandle.restype = w.BOOL
    api.GetFileType.argtypes = [w.HANDLE]
    api.GetFileType.restype = w.DWORD
    api.ReadFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p]
    api.ReadFile.restype = w.BOOL
    api.GetDriveTypeW.argtypes = [w.LPCWSTR]
    api.GetDriveTypeW.restype = w.UINT
    if api.GetDriveTypeW(root.anchor) != 3:  # DRIVE_FIXED; reject mapped remote drives.
        raise OSError("Unsupported private drive")

    def information(handle):
        info = Information()
        if not api.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise OSError("Cannot inspect private handle")
        return info

    with ExitStack() as handles:
        def open_handle(path, *, directory):
            # OPEN_EXISTING; FILE_SHARE_READ only, OPEN_REPARSE_POINT and
            # BACKUP_SEMANTICS so links/junctions are inspected, never followed.
            handle = api.CreateFileW("\\\\?\\" + str(path), 0x80 if directory else 0x80000000,
                                     1, None, 3, 0x00200000 | 0x02000000, None)
            if handle == ctypes.c_void_p(-1).value:
                raise OSError("Cannot open private handle")
            handles.callback(api.CloseHandle, handle)
            info = information(handle)
            if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory or api.GetFileType(handle) != 1:
                raise OSError("Unsafe private handle")
            if not directory and (info.links != 1 or (info.size_high << 32 | info.size_low) > limit):
                raise OSError("Unsafe private file")
            return handle, info

        current = Path(root.anchor)
        open_handle(current, directory=True)
        for part in (*root.parts[1:], *parts[:-1]):
            current /= part
            open_handle(current, directory=True)
        handle, before = open_handle(current / parts[-1], directory=False)
        chunks, size = [], 0
        buffer = ctypes.create_string_buffer(65536)
        while True:
            count = w.DWORD()
            if not api.ReadFile(handle, buffer, min(65536, limit - size + 1), ctypes.byref(count), None):
                raise OSError("Cannot read private handle")
            if not count.value:
                break
            size += count.value
            if size > limit:
                raise OSError("Private file exceeds limit")
            chunks.append(buffer.raw[:count.value])
        after = information(handle)
        def identity(info):
            return (info.volume, info.index_high, info.index_low, info.size_high,
                    info.size_low, info.written.dwHighDateTime, info.written.dwLowDateTime, info.links)
        if identity(before) != identity(after):
            raise OSError("Private file changed")
        return b"".join(chunks)
