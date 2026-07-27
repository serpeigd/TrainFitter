"""Makes agents/ importable as a flat module root, matching how the demo
scripts run (`python agents/run_pipeline_demo.py` adds agents/ to sys.path
automatically; pytest needs the same nudge since it imports from repo root)."""

import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent / "agents"
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))
