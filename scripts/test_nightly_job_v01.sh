#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

BUCKETS_ROOT="${1:-$(pwd)/buckets_graft_merged}"
OUT_DIR="${2:-_nightly_logs}"
SINCE="${3:-2026-04-20}"
UNTIL="${4:-2026-04-21}"

echo "=== nightly_job v0.1 test ==="
echo "repo: $ROOT_DIR"
echo "buckets: $BUCKETS_ROOT"
echo "out_dir: $OUT_DIR"
echo "range: $SINCE -> $UNTIL"
echo ""

echo "=== 1. syntax ==="
python3 -m py_compile scripts/nightly_job.py

echo ""
echo "=== 2. help contains expected flags ==="
python3 scripts/nightly_job.py --help | grep -E -- "--root|--date|--since|--until|--out-dir|--note-preview|--max-preview-chars|--json-summary|--dry-run|--no-dry-run" >/dev/null
echo "help OK"

echo ""
echo "=== 3. normal readonly run ==="
python3 scripts/nightly_job.py \
  --root "$BUCKETS_ROOT" \
  --since "$SINCE" \
  --until "$UNTIL" \
  --out-dir "$OUT_DIR" \
  --note-preview \
  --json-summary \
  --dry-run

echo ""
echo "=== 4. verify latest outputs ==="
MD="$(ls -t "$OUT_DIR"/nightly_*.md | head -1)"
NOTE="$(ls -t "$OUT_DIR"/nightly_note_preview_*.txt | head -1)"
JSON="$(ls -t "$OUT_DIR"/nightly_summary_*.json | head -1)"

test -f "$MD"
test -f "$NOTE"
test -f "$JSON"

echo "markdown: $MD"
echo "note: $NOTE"
echo "json: $JSON"

echo ""
echo "=== 5. verify json safety flags ==="
python3 - "$JSON" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))

assert data["writes_main_brain"] is False
assert data["calls_deepseek"] is False
assert data["calls_hold_grow_trace"] is False
assert data["dry_run"] is True
assert "counts" in data
assert "buckets" in data["counts"]
assert "notes" in data["counts"]
assert "buckets_by_type" in data["counts"]
assert "buckets_by_importance" in data["counts"]

print("json safety flags OK")
print(json.dumps(data["counts"], ensure_ascii=False, indent=2))
PY

echo ""
echo "=== 6. verify no-dry-run is rejected and logged ==="
set +e
python3 scripts/nightly_job.py \
  --root "$BUCKETS_ROOT" \
  --since "$SINCE" \
  --until "$UNTIL" \
  --out-dir "$OUT_DIR" \
  --no-dry-run >/tmp/nightly_job_no_dry_run.out 2>&1
STATUS=$?
set -e

if [ "$STATUS" -eq 0 ]; then
  echo "ERROR: --no-dry-run should fail in v0.1"
  exit 1
fi

ERR="$(find "$OUT_DIR/errors" -type f -name 'nightly_error_*.log' -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -1 || true)"
if [ -z "$ERR" ]; then
  echo "ERROR: expected error log for --no-dry-run"
  exit 1
fi

grep -q -- "--no-dry-run is not supported" "$ERR"
echo "error log OK: $ERR"

echo ""
echo "=== nightly_job v0.1 test PASSED ==="
