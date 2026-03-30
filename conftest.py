from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent


def load_module(relative_path: str, module_name: str | None = None) -> ModuleType:
    target_path = ROOT / relative_path
    resolved_name = module_name or f"skill_{re.sub(r'[^0-9a-zA-Z]+', '_', relative_path)}"
    spec = importlib.util.spec_from_file_location(resolved_name, target_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {target_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules.pop(resolved_name, None)
    spec.loader.exec_module(module)
    return module
