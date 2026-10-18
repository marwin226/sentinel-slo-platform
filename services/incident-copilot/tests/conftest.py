import os
from pathlib import Path

# Must run before `app.main` is imported anywhere: the module builds the copilot at import time.
os.environ.setdefault("RUNBOOK_DIR", str(Path(__file__).resolve().parents[3] / "docs" / "runbooks"))
