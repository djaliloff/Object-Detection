"""Root-level shim: re-exports everything from backend_api/schemas.py using importlib to avoid circular imports."""
import os
import sys
import importlib.util

_backend = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend_api")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

_schemas_path = os.path.join(_backend, "schemas.py")

_spec = importlib.util.spec_from_file_location("_backend_api_schemas", _schemas_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export all public names
for _name in dir(_mod):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_mod, _name)
