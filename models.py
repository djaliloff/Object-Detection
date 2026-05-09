"""Root-level shim: re-exports everything from backend_api/models.py using importlib to avoid circular imports."""
import os
import sys
import importlib.util

_backend = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend_api")

# First ensure database is loadable from backend_api (models depends on it)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

_models_path = os.path.join(_backend, "models.py")

_spec = importlib.util.spec_from_file_location("_backend_api_models", _models_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export all public model classes
User = _mod.User
Camera = _mod.Camera
CameraGroup = _mod.CameraGroup
Event = _mod.Event
Zone = _mod.Zone
Detection = _mod.Detection
Frame = _mod.Frame
Track = _mod.Track
AuditLog = _mod.AuditLog
