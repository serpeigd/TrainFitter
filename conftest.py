"""Makes agents/ and mcp/ importable as flat module roots, matching how the
demo scripts run (`python agents/run_pipeline_demo.py` adds agents/ to
sys.path automatically; pytest needs the same nudge since it imports from
repo root)."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
for _carpeta in ("agents", "mcp"):
    _ruta = str(REPO_ROOT / _carpeta)
    if _ruta not in sys.path:
        sys.path.insert(0, _ruta)
