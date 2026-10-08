#!/usr/bin/env bash
# Golden + benchmark regression on the official dataset (Person 3 plan, Phase 13).
#
#   evaluation/run_regression.sh [run-name] [baseline-scores.json]
#
# Regenerates the dataset (must be byte-identical to the committed one), runs the deterministic
# modes through `episight batch`, scores them, and exits non-zero if a golden case fails or the
# committed dataset is stale. No API key or database needed. FULL (AI planner) is run separately with
# a key: see evaluation/README.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="${1:-regression}"
if [[ ! "$RUN" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]]; then
  echo "run-name must be a simple directory name (no path separators)" >&2
  exit 2
fi
BASELINE="${2:-$ROOT/evaluation/reports/v0.1.0-pc-0.1.1-backend/scores.json}"
DATASET=v0.1.0
CORPUS=pc-0.1.1
OUT="$ROOT/evaluation/runs/$RUN"
PY="${PYTHON:-python}"
UV="${UV:-uv}"

cd "$ROOT"
$PY data/generator/generate_dataset.py >/dev/null
if ! git diff --quiet -- data/synthetic data/policies data/ground-truth; then
  echo "dataset is stale: regenerated files differ from the committed ones" >&2
  git diff --stat -- data/synthetic data/policies data/ground-truth >&2
  exit 1
fi

# Reuse the named output directory without recursively deleting a computed path.
mkdir -p "$OUT"
cd "$ROOT/apps/api"
for MODE in RULES_ONLY RULES_RETRIEVAL FULL_RULE_PLANNER; do
  $UV run episight batch --out "$OUT" --dataset "$ROOT/data/synthetic/$DATASET" \
    --policies "$ROOT/data/policies/$CORPUS" --mode "$MODE" >/dev/null
done
cd "$ROOT"

ARGS=(--run "$OUT" --ground-truth "data/ground-truth/$DATASET/cases.jsonl")
if [[ ! -f "$BASELINE" ]]; then
  echo "baseline does not exist: $BASELINE" >&2
  exit 2
fi
ARGS+=(--baseline "$BASELINE")
ARGS+=(--require-mode RULES_ONLY --require-mode RULES_RETRIEVAL --require-mode FULL_RULE_PLANNER --fail-on-regression)
$PY evaluation/score.py "${ARGS[@]}"

# Golden cases must pass in the deterministic full-pipeline mode.
mkdir -p "$OUT/golden"
cp "$OUT/FULL_RULE_PLANNER.json" "$OUT/golden/"
$PY evaluation/score.py --run "$OUT/golden" --ground-truth "data/ground-truth/$DATASET/cases.jsonl" --fail-on-golden
