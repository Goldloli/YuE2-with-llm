# Rebuild real recordings with YuE2

YuE2 does not ship an audio-to-semantic-token encoder. The community
[realaudio pack](https://huggingface.co/Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4)
fills that gap: a MERT-v2-FullSong head that tokenizes real audio into YuE2's
semantic code space, plus a NAR-branch LoRA so the decoder renders
real-production latents faithfully. Together they let you take a recording,
extract its semantics, and re-render it through YuE2's own sampler, CFG and
VAE — a *rebuild*, not a bit-exact replication.

Weights are CC BY-NC 4.0 (derived from YuE2-3B); non-commercial use only.

## Install the pack

```bash
tools/download_extras.sh        # fetches models/YuE2-Realaudio/ (head + NAR LoRA + neighbour tables)
```

The MERT encoder (`models/MERT-v2-FullSong`) and the transcription environment
(`.venv-sheetsage2`) are the same ones the SheetSage2 stack uses; encoding runs
entirely inside that environment.

## CLI

```bash
# 1. encode a recording into semantic tokens (25 codes/second)
.venv/bin/python tools/realaudio.py encode path/to/song.flac --output work/song/tokens.npy

# 2. re-render the tokens through the NAR branch with the LoRA folded
.venv/bin/python tools/realaudio.py rebuild work/song/tokens.npy --output work/song/rebuild.flac
```

`encode` prints progress as JSON lines; `rebuild` reports token count, audio
length and wall time. Encoding a 3.5-minute track takes well under a minute on
Apple Silicon CPU; rendering scales with the NAR branch (roughly 1x realtime
on MPS at default settings).

## Web app

Uploads carry a **Rebuild with YuE2** button in the detail panel. It encodes
the upload (cached as `uploads/<id>/realaudio/tokens.npy`, re-used while the
audio is unchanged), folds the LoRA, renders, and files the result as a new
song entry with a `Semantic frames` row in its technical details. Rebuild
always runs on the PyTorch pipeline — the MLX backend has no LoRA injection.
The resident model is restored bit-exactly after each rebuild.

## Token layout and fidelity

- Codes are int32 indices into YuE2's semantic vocabulary, 25 per second
  (frame count = duration x 25).
- The head is a per-frame classifier: held-out top-1 accuracy is ~19%, but
  near-miss codes render almost identically (publisher ear tests of NAR
  round-trips sit near 95%). Treat rebuilds as *restyled re-synthesis*, not
  faithful copies — melodic content roughly follows the source.
- The NAR LoRA also keeps ordinary generation intact: it is folded only for
  the duration of a rebuild, then restored.

## Training an artist AR LoRA (external GPU)

The pack's tokenizer is the intended data front-end for training AR LoRAs on
your own catalogue. The publisher's training scripts require a CUDA box
(24 GB), Demucs vocal separation and MMS forced alignment, and are outside
this repository's scope; `tokens.npy` from `encode` is the corpus interface.
Once trained, keep the AR LoRA in `models/loras/<name>/lora.safetensors` —
the web app's existing LoRA picker can apply it to normal generation.
