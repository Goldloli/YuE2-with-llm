#!/bin/bash
# Resume the YuE2-3B model.safetensors chunked download: every part file is
# continued at its exact byte offset, stalled transfers are cut by
# --speed-limit, and finished parts are skipped untouched.
set -u
BASE="https://hf-mirror.com"
REPO=m-a-p/YuE2-3B
FILE=model.safetensors
OUT=/Volumes/worknie/Desktop/ai_code/yue/models/YuE2-3B/model.safetensors
SIZE=7261441640
CHUNKS=16
chunk=$(( (SIZE + CHUNKS - 1) / CHUNKS ))

pids=()
for i in $(seq 0 $(( CHUNKS - 1 ))); do
  start=$(( i * chunk )); end=$(( (i + 1) * chunk - 1 ))
  [ $end -ge $SIZE ] && end=$(( SIZE - 1 ))
  part="$OUT.part.$(printf %03d $i)"
  want=$(( end - start + 1 ))
  (
    for _ in $(seq 1 60); do
      have=$( [ -f "$part" ] && stat -f %z "$part" || echo 0 )
      [ "$have" -ge "$want" ] && exit 0
      curl -sSL --speed-limit 32768 --speed-time 25 --max-time 900 \
        -r "$(( start + have ))-$end" \
        "$BASE/$REPO/resolve/main/$FILE" >> "$part" 2>/dev/null || true
      sleep 2
    done
    have=$( [ -f "$part" ] && stat -f %z "$part" || echo 0 )
    [ "$have" -ge "$want" ]
  ) &
  pids+=($!)
done

fail=0
for p in "${pids[@]}"; do wait "$p" || fail=1; done
[ $fail -eq 0 ] || { echo "CHUNKS INCOMPLETE" >&2; exit 1; }

cat "$OUT".part.* > "$OUT" && rm -f "$OUT".part.*
got=$(stat -f %z "$OUT")
[ "$got" = "$SIZE" ] || { echo "SIZE MISMATCH: $got != $SIZE" >&2; exit 1; }
echo "RESUME_DONE: $OUT ($got bytes)"
