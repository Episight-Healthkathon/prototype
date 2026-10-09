"""Run with uv from apps/api: uv run python ../web/scripts/generate-demo.py.

Fixtures are generated from runtime data and the deterministic engine. Ground truth is never read.
"""
import json
import shutil
import tempfile
from pathlib import Path

from episight.devtools.contract_export import export

root = Path(__file__).resolve().parents[3]
destination = root / "apps/web/public/demo"
with tempfile.TemporaryDirectory(prefix="episight-web-fixtures-") as temporary:
    staging = Path(temporary)
    export(staging, root / "data/synthetic/v0.1.0", root / "data/policies/pc-0.1.1")
    index = staging / "fixtures/index.json"
    metadata = json.loads(index.read_text(encoding="utf-8"))
    metadata["note"] = "Official synthetic v0.1.0; real deterministic engine output. Demo playback is not a new API run."
    index.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    shutil.copytree(staging / "fixtures", destination, dirs_exist_ok=True)
print(f"Generated demo fixtures in {destination}")
