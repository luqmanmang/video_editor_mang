#!/usr/bin/env bash
# Private A/B comparison of TikTok-style Kauthar headline, no public release.
set -euo pipefail
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
APP="$ROOT/remotion-app"
TARGET="$ROOT/framework/.runtime/kauthar_headline_ab"
AUDIO="$APP/public/media/kauthar_ab_master_audio.m4a"
mkdir -p "$TARGET"
echo "STAGE:SOURCE_PREFLIGHT"
test -s "$AUDIO"
printf '%s  %s\n' ae0f57707d10cdf8cf7c7a5f335e9e16c0a558cb7fca3430d7c199da521e51ca "$AUDIO" | sha256sum --check --status
echo "GATE:original_audio_hash=PASS"
test -s "$APP/public/media/00_prediction_setup.mp4"
test -s "$APP/public/media/07_payoff.mp4"
test -s "$APP/public/stock/experience.mp4"
test -s "$APP/public/stock/giving.mp4"
echo "GATE:source_media_present=PASS"
echo "STAGE:CODE_QUALITY"
(cd "$APP" && npm run lint)
echo "GATE:lint_typescript=PASS"
echo "STAGE:RENDER_720"
for variant in A B; do
  out="$TARGET/kauthar_headline_"$variant"_720p_private.mp4"
  qa_dir="$TARGET/qa_$variant"
  mkdir -p "$qa_dir"
  if [[ -e "$out" ]]; then
    echo "GATE:output_would_overwrite=FAIL"
    echo "Output exists: $out. Refuse overwrite; use a new run folder."
    exit 2
  fi
  echo "Rendering private headline variant $variant..."
  (cd "$APP" && npx remotion render src/index.ts "KautharHeadline"$variant"720" "$out" \
    --codec=h264 --crf=22 --concurrency=2 --scale=1)
  echo "STAGE:QA_$variant"
  python3 "$ROOT/framework/qa_render.py" "$out" --out-dir "$qa_dir" \
    --plan "$ROOT/framework/projects/kauthar_v3/scene_plan_31.json" \
    --width 720 --height 1280
  sha256sum "$out" > "$qa_dir/video.sha256"
  echo "GATE:variant_"$variant"_technical=PASS"
done
echo "METRIC:variants_technical_pass=2"
echo "STAGE:REVIEW_HANDOFF"
echo "GATE:human_review=PENDING"
echo "GATE:source_rights=BLOCKED"
echo "GATE:full_test_private_only=PASS"
echo "OUTPUT_DIR=$TARGET"
