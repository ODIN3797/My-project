"""Optional system libzstd fallback for MCAP chunks.

This is only used when the Python ``zstandard`` package is unavailable. It
requires a trusted OS-provided libzstd; output size is fixed by the MCAP
chunk header and bounded by the caller. The library is never downloaded.
"""
from __future__ import annotations

import ctypes
import ctypes.util


def decompress_zstd(data: bytes, expected_size: int) -> bytes:
    if expected_size < 0 or expected_size > 256 * 1024 * 1024:
        raise ValueError('Invalid declared zstd output size')
    name = ctypes.util.find_library('zstd')
    if not name:
        raise ImportError('Python zstandard module and system libzstd are unavailable')
    try:
        lib = ctypes.CDLL(name)
    except OSError as exc:
        raise ImportError('Could not load the system libzstd library') from exc
    lib.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.c_void_p, ctypes.c_size_t]
    lib.ZSTD_decompress.restype = ctypes.c_size_t
    lib.ZSTD_isError.argtypes = [ctypes.c_size_t]
    lib.ZSTD_isError.restype = ctypes.c_uint
    # Buffers own their memory throughout the native call.
    src = ctypes.create_string_buffer(data)
    dst = ctypes.create_string_buffer(max(1, expected_size))
    result = lib.ZSTD_decompress(dst, expected_size, src, len(data))
    if lib.ZSTD_isError(result):
        raise ValueError('Invalid zstd-compressed MCAP chunk')
    if result != expected_size:
        raise ValueError(f'zstd output length mismatch ({result} vs {expected_size})')
    return dst.raw[:result]
