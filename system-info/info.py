import platform
import os
import json

def get_system_info():
    info = {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version()
    }

    # Try to add memory info if possible without external deps
    if platform.system() == "Windows":
        info["cpu_cores"] = os.cpu_count()
    elif platform.system() == "Linux":
        info["cpu_cores"] = os.cpu_count()
    elif platform.system() == "Darwin":
        info["cpu_cores"] = os.cpu_count()

    return info

if __name__ == "__main__":
    sys_data = get_system_info()
    print(json.dumps(sys_data, indent=2))
