#!/usr/bin/env bash
# One RSI run against a cloud OpenAI-compatible endpoint.
#
#   export VIRTU_RSI_BASE_URL=https://<host>:<port>/v1
#   export VIRTU_RSI_MODEL_ID=<served model id>
#   export VIRTU_EVAL_API_KEY=<bearer token>     # only if the endpoint requires one
#   bash cloud_train_pack/rsi_cloud_run.sh
#
# The probe runs first and must pass: an endpoint that cannot report a pinned model id
# and answer one scored call is not measurable, so the loop never starts against it.
set -euo pipefail

: "${VIRTU_RSI_BASE_URL:?set VIRTU_RSI_BASE_URL, e.g. https://host:8000/v1}"
: "${VIRTU_RSI_MODEL_ID:?set VIRTU_RSI_MODEL_ID to the id the endpoint serves}"

cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p runs/rsi

echo "[rsi-cloud] endpoint=$VIRTU_RSI_BASE_URL model=$VIRTU_RSI_MODEL_ID stamp=$STAMP"

set +e
"$PY" cloud_train_pack/rsi_cloud_entry.py --probe | tee "runs/rsi/cloud_${STAMP}.probe.json"
PROBE_CODE=${PIPESTATUS[0]}
set -e
if [ "$PROBE_CODE" -ne 0 ]; then
  echo "[rsi-cloud] probe failed (exit $PROBE_CODE); refusing to start the loop" >&2
  exit "$PROBE_CODE"
fi

set +e
"$PY" cloud_train_pack/rsi_cloud_entry.py | tee "runs/rsi/cloud_${STAMP}.run.json"
RUN_CODE=${PIPESTATUS[0]}
set -e

echo "[rsi-cloud] run exit=$RUN_CODE (0 ok / 3 blocked); evidence under runs/rsi/"
exit "$RUN_CODE"
