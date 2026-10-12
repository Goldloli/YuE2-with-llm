#!/bin/bash
# Download YuE2 models from hf-mirror.com, bypassing huggingface_hub (whose
# metadata HEAD requests redirect to the unreachable huggingface.co host).
# Large files are fetched as parallel range chunks and reassembled; the
# pipeline later verifies every sha256 against weights_manifest.json.
set -u
BASE="https://hf-mirror.com"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/models"

fetch_small() { # repo file out
  local repo=$1 file=$2 out=$3
  mkdir -p "$(dirname "$out")"
  for _ in $(seq 1 10); do
    curl -sSL --retry 3 --retry-all-errors --retry-delay 2 -C - \
      --max-time 600 "$BASE/$repo/resolve/main/$file" -o "$out" && return 0
    sleep 3
  done
  echo "FAILED: $repo/$file" >&2
  return 1
}

fetch_big() { # repo file out size chunks
  local repo=$1 file=$2 out=$3 size=$4 chunks=$5
  local chunk=$(( (size + chunks - 1) / chunks ))
  local pids=() i start end
  rm -f "$out".part.*
  for i in $(seq 0 $((chunks - 1))); do
    start=$(( i * chunk )); end=$(( (i + 1) * chunk - 1 ))
    [ $start -ge $size ] && break
    [ $end -ge $size ] && end=$(( size - 1 ))
    (
      for _ in $(seq 1 8); do
        curl -sSL --retry 3 --retry-all-errors --retry-delay 2 \
          -r "$start-$end" -o "$out.part.$(printf %03d $i)" \
          "$BASE/$repo/resolve/main/$file" && exit 0
        sleep 3
      done
      exit 1
    ) &
    pids+=($!)
  done
  local fail=0 p
  for p in "${pids[@]}"; do wait "$p" || fail=1; done
  [ $fail -eq 0 ] || { echo "FAILED: $repo/$file (chunk error)" >&2; return 1; }
  cat "$out".part.* > "$out" && rm -f "$out".part.*
  local got
  got=$(stat -f %z "$out")
  [ "$got" = "$size" ] || { echo "SIZE MISMATCH: $out ($got != $size)" >&2; return 1; }
  echo "done: $out ($(( size / 2**20 )) MiB)"
}

main_size=7261441640   # m-a-p/YuE2-3B model.safetensors
vae_size=530512720     # m-a-p/YuE2-Vae model.safetensors

mkdir -p "$DEST/YuE2-3B/licenses" "$DEST/YuE2-Vae/licenses"

fail=0
for f in config.json generation_config.json yue2_generation_config.json \
         weights_manifest.json qwen.tiktoken modeling_yue2.py \
         LICENSE THIRD_PARTY_NOTICES.md; do
  fetch_small m-a-p/YuE2-3B "$f" "$DEST/YuE2-3B/$f" || fail=1
done
for f in stable-audio-tools-MIT.txt SnakeBeta-NVIDIA-MIT.txt; do
  fetch_small m-a-p/YuE2-3B "licenses/$f" "$DEST/YuE2-3B/licenses/$f" || fail=1
done
for f in config.json weights_manifest.json modeling_vae.py \
         LICENSE THIRD_PARTY_NOTICES.md; do
  fetch_small m-a-p/YuE2-Vae "$f" "$DEST/YuE2-Vae/$f" || fail=1
done
for f in stable-audio-tools-MIT.txt SnakeBeta-NVIDIA-MIT.txt; do
  fetch_small m-a-p/YuE2-Vae "licenses/$f" "$DEST/YuE2-Vae/licenses/$f" || fail=1
done

[ $fail -eq 0 ] || { echo "small files incomplete" >&2; exit 1; }

fetch_big m-a-p/YuE2-Vae model.safetensors "$DEST/YuE2-Vae/model.safetensors" $vae_size 8 || exit 1
fetch_big m-a-p/YuE2-3B model.safetensors "$DEST/YuE2-3B/model.safetensors" $main_size 16 || exit 1

echo "DOWNLOAD_ALL_DONE"
