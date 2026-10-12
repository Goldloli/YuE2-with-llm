#!/bin/bash
# Optional extras for YuE2 Studio, fetched from hf-mirror.com like download_models.sh:
#   - m-a-p/YuE2-Vae-legacy      the benchmark-protocol audio decoder (Settings → Decoder)
#   - community LoRA adapters    style adapters for Create → Advanced → More Options
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

size_of() { # repo file -> bytes on stdout
  curl -sIL --max-time 60 "$BASE/$1/resolve/main/$2" \
    | tr -d '\r' | awk 'tolower($1)=="content-length:"{n=$2} END{print n}'
}

fetch_big() { # repo file out [size chunks]
  local repo=$1 file=$2 out=$3 size=${4:-} chunks=${5:-8}
  mkdir -p "$(dirname "$out")"
  [ -z "$size" ] && size=$(size_of "$repo" "$file")
  if [ -n "$size" ] && [ -f "$out" ] && [ "$(stat -f %z "$out")" = "$size" ]; then
    echo "skip: $out (already complete)"
    return 0
  fi
  if [ -z "$size" ] || [ "$size" -lt 1024 ] 2>/dev/null; then
    echo "cannot determine size for $repo/$file" >&2
    return 1
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

fail=0

# ----- YuE2-Vae-legacy -----
mkdir -p "$DEST/YuE2-Vae-legacy/licenses"
for f in config.json weights_manifest.json modeling_vae.py LICENSE THIRD_PARTY_NOTICES.md; do
  fetch_small m-a-p/YuE2-Vae-legacy "$f" "$DEST/YuE2-Vae-legacy/$f" || fail=1
done
for f in stable-audio-tools-MIT.txt SnakeBeta-NVIDIA-MIT.txt; do
  fetch_small m-a-p/YuE2-Vae-legacy "licenses/$f" "$DEST/YuE2-Vae-legacy/licenses/$f" || fail=1
done
if [ -f "$DEST/YuE2-Vae-legacy/weights_manifest.json" ]; then
  legacy_size=$(python3 -c "import json;print(json.load(open('$DEST/YuE2-Vae-legacy/weights_manifest.json'))['files']['model.safetensors']['bytes'])")
  fetch_big m-a-p/YuE2-Vae-legacy model.safetensors "$DEST/YuE2-Vae-legacy/model.safetensors" "$legacy_size" 8 || fail=1
else
  fail=1
fi

# ----- YuE2-Vae-merge (default x legacy weight merge, community release) -----
mkdir -p "$DEST/YuE2-Vae-merge/licenses"
for f in config.json weights_manifest.json modeling_vae.py LICENSE THIRD_PARTY_NOTICES.md; do
  fetch_small Mothersuperior/YuE2-Vae-merge-0.666 "$f" "$DEST/YuE2-Vae-merge/$f" || fail=1
done
for f in stable-audio-tools-MIT.txt SnakeBeta-NVIDIA-MIT.txt; do
  fetch_small Mothersuperior/YuE2-Vae-merge-0.666 "licenses/$f" "$DEST/YuE2-Vae-merge/licenses/$f" || fail=1
done
if [ -f "$DEST/YuE2-Vae-merge/weights_manifest.json" ]; then
  merge_size=$(python3 -c "import json;print(json.load(open('$DEST/YuE2-Vae-merge/weights_manifest.json'))['files']['model.safetensors']['bytes'])")
  fetch_big Mothersuperior/YuE2-Vae-merge-0.666 model.safetensors "$DEST/YuE2-Vae-merge/model.safetensors" "$merge_size" 8 || fail=1
else
  fail=1
fi

# ----- realaudio tokenizer pack (MERT -> semantic tokens + NAR LoRA) -----
mkdir -p "$DEST/YuE2-Realaudio/assets"
fetch_small Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4 README.md \
            "$DEST/YuE2-Realaudio/README.md" || true
fetch_small Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4 tokenizer_head_joint_v9.bf16.safetensors \
            "$DEST/YuE2-Realaudio/tokenizer_head_joint_v9.bf16.safetensors" || fail=1
fetch_small Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4 nar_lora_joint_v9.bf16.safetensors \
            "$DEST/YuE2-Realaudio/nar_lora_joint_v9.bf16.safetensors" || fail=1
for f in sem_nbr_idx.npy sem_nbr_cos.npy; do
  fetch_small Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4 "assets/$f" \
              "$DEST/YuE2-Realaudio/assets/$f" || fail=1
done

# ----- LoRA adapters -----
fetch_big pduncan/YuE2_Deathmetalv1_lora deathmetalv1_step-000600.safetensors \
          "$DEST/loras/deathmetal-v1/lora.safetensors" 278968264 4
fetch_small pduncan/YuE2_Deathmetalv1_lora README.md "$DEST/loras/deathmetal-v1/README.md" || true

fetch_big storagejuju/yue2-jpop-t4-lora yue2_jpop_t4.safetensors \
          "$DEST/loras/jpop-t4/lora.safetensors" "" 4
fetch_small storagejuju/yue2-jpop-t4-lora training_config.json "$DEST/loras/jpop-t4/training_config.json" || true

fetch_big Mothersuperior/YuE2-instrumental-cot-full-loras ar_lora_inst_v3abc.safetensors \
          "$DEST/loras/instrumental-v3abc/lora.safetensors" "" 4
fetch_small Mothersuperior/YuE2-instrumental-cot-full-loras README.md "$DEST/loras/instrumental-v3abc/README.md" || true

echo "EXTRAS_DONE fail=$fail"
exit $fail
