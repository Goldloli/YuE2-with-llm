#!/usr/bin/env python3
"""Generate one song with the MLX backend, streaming JSON progress on stdout.

Run with .venv-mlx/bin/python (Apple Silicon only). web/server.py starts this
as a subprocess, mirroring how SheetSage2 transcription runs in its own env.

Output lines (one JSON object per line):
  {"phase": "planning"|"composing"|"synthesizing"|"decoding", ...counters}
  {"phase": "done", "audio_seconds": s, "wall_seconds": s}
  {"phase": "error", "error": "..."}
Artifacts written to --out-dir: audio.flac, score.abc (when planned), result.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from pathlib import Path

SAMPLE_RATE = 48000


def emit(obj):
    print(json.dumps(obj), flush=True)


def localized_style(args):
    """Translate args.style per --style-language, keeping any server-supplied original."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from yue2.style_localization import resolve_style_original
    return resolve_style_original(args.style, args.style_original, args.style_language)


def plan_instrumental(pipe, style, lyrics, cot, seed, out_dir):
    """Plan a score and move Vocal notes to the Ins voice before rendering.

    Returns (abc_text, abc_truncated) — the converted score on an effective
    transfer, otherwise the original plan. Writes score.model.abc and
    transfer.json only when the Vocal voice actually had notes.
    """
    from generate import generate_tokens, token_prefix
    tok = pipe.tokenizer
    counts = [0]

    def on_plan_token(_phase, _token):
        counts[0] += 1
        if counts[0] % 200 == 0:
            emit({"phase": "planning", "tokens": counts[0]})

    emit({"phase": "planning"})
    prefix = token_prefix(tok, style, lyrics, cot)
    ids, abc_truncated = generate_tokens(pipe.model, prefix, pipe.abc_sampling, seed, "abc",
                                         on_token=on_plan_token)
    planned = tok.decode(ids)
    scripts = Path(__file__).resolve().parents[1] / "skills" / "yue2-music" / "instrumental" / "scripts"
    try:
        sys.dont_write_bytecode = True  # keep the distributable skill dir pyc-free
        sys.path.insert(0, str(scripts))
        from instrumentalize import convert_score
        converted, check = convert_score(planned)
    except Exception as exc:  # noqa: BLE001 - transfer failure must not block generation
        emit({"phase": "instrumental_fallback", "error": f"{type(exc).__name__}: {exc}"})
        return planned, abc_truncated
    if not check["vocal_notes_before"]:
        return planned, abc_truncated
    (out_dir / "score.model.abc").write_text(planned, encoding="utf-8")
    (out_dir / "transfer.json").write_text(json.dumps(check, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    return converted, abc_truncated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True, help="dir containing the MLX variant subdir")
    ap.add_argument("--variant", default="8bit", choices=["bf16", "8bit", "4bit"])
    ap.add_argument("--style", required=True)
    ap.add_argument("--style-original", default=None,
                    help="Pre-translation style text, persisted for audit when already localized")
    ap.add_argument("--style-language", default="auto", choices=["auto", "en", "off"],
                    help="auto translates Chinese style prompts to English tags; en/off pass through")
    ap.add_argument("--lyrics", default="")
    ap.add_argument("--cot", default="full", choices=["off", "melody", "full"])
    ap.add_argument("--seed", type=int, default=831001)
    ap.add_argument("--cfg-scale", type=float, default=None)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--top-p", type=float, default=None)
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--instrumental", action="store_true",
                    help="plan a score, move Vocal notes to the Ins voice, then render it")
    ap.add_argument("--max-semantic-tokens", type=int, default=None)
    ap.add_argument("--abc-file", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    style, style_original = localized_style(args)

    pkg = args.model / args.variant
    if not (pkg / "model.safetensors").exists():
        emit({"phase": "error", "error": f"MLX weights not found under {pkg}"})
        return 2

    sys.path.insert(0, str(args.model))
    import numpy as np
    import soundfile as sf
    from generate import Sampling, Yue2Pipeline

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    timings = {}
    marks = {}
    truncated = {"abc": False, "semantic": False}
    rx_tokens = re.compile(r"^\[(\w+)\] (\d+) tokens, ([\d.]+) tok/s$")
    rx_frames = re.compile(r"^\[nar\] (\d+) frames \(([\d.]+)s\)")

    def note(kind):
        timings[kind] = time.perf_counter()

    def log(msg):
        m = rx_tokens.match(msg)
        if m:
            phase = "planning" if m.group(1) == "abc" else "composing"
            emit({"phase": phase, "tokens": int(m.group(2)), "rate": float(m.group(3))})
            return
        m = rx_frames.match(msg)
        if m:
            timings["nar_start"] = timings.get("nar_start", time.perf_counter())
            emit({"phase": "synthesizing", "frames": int(m.group(1)), "seconds": float(m.group(2))})
            return
        if msg.startswith("[nar] step"):
            step, total = msg.split()[2].split("/")
            emit({"phase": "synthesizing", "step": int(step), "steps": int(total)})
            return
        if msg.startswith("[plan]"):
            if "hit max_tokens" in msg:
                truncated["abc"] = True
            else:
                note("plan_start")
            return
        if msg.startswith("[semantic]"):
            if "hit max_tokens" in msg:
                truncated["semantic"] = True
            else:
                timings["semantic_start"] = timings.get("semantic_start", time.perf_counter())
            return
        if msg.startswith("[vae]"):
            timings["vae_start"] = time.perf_counter()
            emit({"phase": "decoding"})
            return
        print(msg, file=sys.stderr, flush=True)

    start = time.perf_counter()
    try:
        pipe = Yue2Pipeline(pkg, log=log)

        if args.plan_only:
            if args.cot == "off":
                raise ValueError("plan_only needs cot melody or full")
            from generate import generate_tokens, token_prefix
            tok = pipe.tokenizer
            counts = [0]

            def on_plan_token(_phase, _token):
                counts[0] += 1
                if counts[0] % 200 == 0:
                    emit({"phase": "planning", "tokens": counts[0]})

            emit({"phase": "planning"})
            prefix = token_prefix(tok, style, args.lyrics, args.cot)
            ids, truncated_abc = generate_tokens(pipe.model, prefix, pipe.abc_sampling,
                                                 args.seed, "abc", on_token=on_plan_token)
            abc_text = tok.decode(ids)
            (out_dir / "score.abc").write_text(abc_text, encoding="utf-8")
            timings["total"] = time.perf_counter() - start
            (out_dir / "result.json").write_text(json.dumps({
                "status": "complete", "plan_only": True, "backend": f"mlx-{args.variant}",
                "audio_seconds": None, "abc_tokens": len(ids),
                "truncated": {"abc": bool(truncated_abc), "semantic": False}, "timing": timings,
            }, indent=2), encoding="utf-8")
            emit({"phase": "done", "plan_only": True, "abc_tokens": len(ids)})
            return 0

        sampling = pipe.semantic_sampling
        overrides = {}
        if args.temperature is not None:
            overrides["temperature"] = args.temperature
        if args.top_p is not None:
            overrides["top_p"] = args.top_p
        if args.top_k is not None:
            overrides["top_k"] = args.top_k
        if args.max_semantic_tokens:
            overrides["max_tokens"] = args.max_semantic_tokens
        if overrides:
            sampling = Sampling(**{**sampling.__dict__, **overrides})
        abc = args.abc_file.read_text(encoding="utf-8") if args.abc_file else None
        if args.instrumental and abc is None and args.cot != "off":
            abc, abc_truncated = plan_instrumental(pipe, style, args.lyrics, args.cot,
                                                   args.seed, out_dir)
            truncated["abc"] = bool(abc_truncated)
        emit({"phase": "planning"})
        audio, meta = pipe(style=style, lyrics=args.lyrics, cot=args.cot, seed=args.seed,
                           abc=abc, cfg_scale=args.cfg_scale, semantic_sampling=sampling,
                           steps=args.steps)
        note("decode_done")
        timings["total"] = time.perf_counter() - start
        audio_np = np.array(audio, dtype=np.float32)
        sf.write(str(out_dir / "audio.flac"), audio_np, SAMPLE_RATE, subtype="PCM_24")
        if meta.get("abc"):
            (out_dir / "score.abc").write_text(meta["abc"], encoding="utf-8")
        np.save(out_dir / "latent.npy", np.array(meta["latents"], dtype=np.float32))
        audio_seconds = len(audio_np) / SAMPLE_RATE
        request_record = {
            "style": style, "lyrics": args.lyrics, "cot": args.cot, "seed": args.seed,
            "cfg_scale": args.cfg_scale, "abc": bool(abc),
            "sampling": {k: v for k, v in (("temperature", args.temperature), ("top_p", args.top_p),
                                           ("top_k", args.top_k), ("max_semantic_tokens", args.max_semantic_tokens),
                                           ("steps", args.steps)) if v is not None},
        }
        if style_original:
            request_record["style_original"] = style_original
        (out_dir / "request.json").write_text(json.dumps(request_record, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
        (out_dir / "result.json").write_text(json.dumps({
            "status": "complete", "backend": f"mlx-{args.variant}", "sample_rate": SAMPLE_RATE,
            "audio_seconds": audio_seconds, "semantic_tokens": len(meta["codec"]),
            "truncated": truncated, "timing": timings,
        }, indent=2), encoding="utf-8")
        emit({"phase": "done", "audio_seconds": audio_seconds,
              "wall_seconds": timings["total"], "semantic_tokens": len(meta["codec"])})
        return 0
    except Exception as exc:  # noqa: BLE001 - report any failure to the server
        traceback.print_exc()
        emit({"phase": "error", "error": f"{type(exc).__name__}: {exc}"})
        return 1


if __name__ == "__main__":
    sys.exit(main())
