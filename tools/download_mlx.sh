#!/bin/bash
# One-off feasibility test for ahmadw/YuE2-3B-MLX (Apple MLX port of YuE2-3B).
# Uses curl against hf-mirror.com; huggingface_hub fails here because its HEAD
# metadata requests redirect to the unreachable huggingface.co host.
#
# Variants (models/YuE2-3B-MLX/<variant>/, picked in Settings > Model & performance):
#   8bit  this script downloads it (recommended default). 20s-song benchmarks:
#         8bit ~16-18s, bf16 ~28-29s, PyTorch MPS ~61s (same prompt/seed) --
#         8bit is ~1.7x faster than bf16 and ~3.6x faster than torch.
#   bf16  full-precision conversion (no accuracy loss, ~70% slower than 8bit):
#         cd models/YuE2-3B-MLX && ../../.venv-mlx/bin/python convert.py \
#           --model ../YuE2-3B --vae ../YuE2-Vae --output bf16
#   4bit  memory saver (~-q --bits 4; NAR stays 8-bit); needs ~2.5GB less RAM
#         but drifts on the flow-matching path -- use only when memory-bound.
set -u
BASE="https://hf-mirror.com"
REPO="ahmadw/YuE2-3B-MLX"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/models/YuE2-3B-MLX"
REPO_DIR="$WORK"
mkdir -p "$REPO_DIR/8bit"

if [ ! -x "$ROOT/.venv-mlx/bin/python" ]; then
  python3 -m venv "$ROOT/.venv-mlx"
fi
PY="$ROOT/.venv-mlx/bin/python"

echo "== installing mlx =="
"$PY" -m pip install -q --upgrade pip 2>&1 | tail -1
"$PY" -m pip install -q mlx tiktoken numpy soundfile \
  || "$PY" -m pip install -q -i https://pypi.tuna.tsinghua.edu.cn/simple mlx tiktoken numpy soundfile
"$PY" -c "import mlx.core as mx, mlx.nn; print('mlx ready')"

fetch_small() { # file out
  local file=$1 out=$2
  mkdir -p "$(dirname "$out")"
  for _ in $(seq 1 10); do
    curl -sSL --retry 3 --retry-all-errors --retry-delay 2 -C - \
      --max-time 600 "$BASE/$REPO/resolve/main/$file" -o "$out" && return 0
    sleep 3
  done
  echo "FAILED: $file" >&2
  return 1
}

fetch_big() { # file out size chunks
  local file=$1 out=$2 size=$3 chunks=${4:-8}
  mkdir -p "$(dirname "$out")"
  if [ -f "$out" ] && [ "$(stat -f %z "$out")" = "$size" ]; then
    echo "skip: $out (already complete)"; return 0
  fi
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
          "$BASE/$REPO/resolve/main/$file" && exit 0
        sleep 3
      done
      exit 1
    ) &
    pids+=($!)
  done
  local fail=0 p
  for p in "${pids[@]}"; do wait "$p" || fail=1; done
  [ $fail -eq 0 ] || { echo "FAILED: $file (chunk error)" >&2; return 1; }
  cat "$out".part.* > "$out" && rm -f "$out".part.*
  local got
  got=$(stat -f %z "$out")
  [ "$got" = "$size" ] || { echo "SIZE MISMATCH: $out ($got != $size)" >&2; return 1; }
  echo "done: $out ($(( size / 2**20 )) MiB)"
}

echo "== downloading MLX inference code =="
for f in generate.py convert.py test_parity.py yue2_model.py yue2_vae.py README.md; do
  fetch_small "$f" "$REPO_DIR/$f" || exit 1
done

echo "== downloading 8bit weights =="
for f in config.json qwen.tiktoken vae_config.json yue2_generation_config.json; do
  fetch_small "8bit/$f" "$REPO_DIR/8bit/$f" || exit 1
done
fetch_big 8bit/model.safetensors "$REPO_DIR/8bit/model.safetensors" 4264488042 12 || exit 1
fetch_big 8bit/vae.safetensors "$REPO_DIR/8bit/vae.safetensors" 265441814 4 || exit 1

echo "MLX_SETUP_DONE"
