"""Root-level shim: re-exports everything from backend_api/database.py using importlib to avoid circular imports."""
import os
import sys
import importlib.util

_backend = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend_api")
_db_path = os.path.join(_backend, "database.py")

_spec = importlib.util.spec_from_file_location("_backend_api_database", _db_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export all public names
get_db = _mod.get_db
engine = _mod.engine
Base = _mod.Base
SessionLocal = _mod.SessionLocal
