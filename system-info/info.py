from __future__ import annotations

import ctypes
import json
import os
import platform
import socket
import sys
from typing import Any


def detect_total_memory_bytes() -> int | None:
    system_name = platform.system()

    if system_name == "Windows":
        kernel32 = getattr(getattr(ctypes, "windll", None), "kernel32", None)
        if kernel32 is None:
            return None

        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        memory_status = MemoryStatusEx()
        memory_status.dwLength = ctypes.sizeof(MemoryStatusEx)
        if kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status)):
            return int(memory_status.ullTotalPhys)
        return None

    if hasattr(os, "sysconf"):
        try:
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
            physical_pages = int(os.sysconf("SC_PHYS_PAGES"))
            if page_size > 0 and physical_pages > 0:
                return page_size * physical_pages
        except (AttributeError, OSError, TypeError, ValueError):
            pass

    if system_name == "Linux":
        try:
            with open("/proc/meminfo", encoding="utf-8") as meminfo:
                for line in meminfo:
                    if not line.startswith("MemTotal:"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1]) * 1024
        except (OSError, ValueError):
            return None

    return None


def detect_python_environment() -> dict[str, str] | None:
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        return {"type": "conda", "path": conda_prefix}

    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        return {"type": "venv", "path": virtual_env}

    base_prefix = getattr(sys, "base_prefix", sys.prefix)
    if sys.prefix != base_prefix:
        return {"type": "venv", "path": sys.prefix}

    return None


def get_system_info() -> dict[str, Any]:
    system_name = platform.system()
    info: dict[str, Any] = {
        "os": system_name,
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "python_prefix": sys.prefix,
    }

    if system_name in {"Windows", "Linux", "Darwin"}:
        info["cpu_cores"] = os.cpu_count()

    total_memory_bytes = detect_total_memory_bytes()
    if total_memory_bytes is not None:
        info["memory_total_bytes"] = total_memory_bytes
        info["memory_total_gb"] = round(total_memory_bytes / (1024 ** 3), 2)

    python_environment = detect_python_environment()
    if python_environment is not None:
        info["python_environment"] = python_environment

    return info


def main() -> int:
    print(json.dumps(get_system_info(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    main()
