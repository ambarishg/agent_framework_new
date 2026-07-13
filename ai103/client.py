from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


_ROOT_DIR = Path(__file__).resolve().parent.parent
_ROOT_CLIENT = _ROOT_DIR / "client.py"

if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

_SPEC = spec_from_file_location("_root_client", _ROOT_CLIENT)

if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load client module from {_ROOT_CLIENT}")

_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

for _name in dir(_MODULE):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_MODULE, _name)
