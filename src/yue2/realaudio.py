"""Real-audio tooling for YuE2: NAR LoRA folding and rebuild rendering.

The v9 joint pack (Mothersuperior/yue2-mothersuperior-realaudio-tokenizer-v4)
pairs a MERT-based tokenizer head with a rank-32 LoRA for the NAR branch plus
full replacement weights for the vae2llm/llm2vae bridges. Folding mutates the
resident model, so a rebuild run MUST snapshot / restore around it.
"""
from __future__ import annotations

import contextlib

import numpy as np
import torch

BRIDGES = ("vae2llm", "llm2vae")


def load_nar_lora(path):
    """Return (deltas, bridges) from a v9-format pack.

    deltas: [(module_base, A, B)] where module_base is a dotted path below the
    top-level model (e.g. "layers.3.nar_self_attn.q_proj").
    bridges: {"vae2llm": {"weight", "bias"}, "llm2vae": {...}} full replacements.
    """
    from safetensors.torch import load_file
    state = load_file(str(path), device="cpu")
    pairs = {}
    for key, value in state.items():
        for bridge in BRIDGES:
            if key.startswith(bridge + "."):
                break
        else:
            for suffix in (".lora_A", ".lora_B"):
                if key.endswith(suffix):
                    pairs.setdefault(key[: -len(suffix)], {})[suffix.lstrip(".")] = value.float()
                    break
    deltas = []
    for base, ab in sorted(pairs.items()):
        if "lora_A" not in ab or "lora_B" not in ab:
            raise ValueError(f"LoRA pair is incomplete for {base}")
        deltas.append((base, ab["lora_A"], ab["lora_B"]))
    bridges = {}
    for name in BRIDGES:
        entry = {k[len(name) + 1:]: v for k, v in state.items() if k.startswith(name + ".")}
        if "weight" not in entry or "bias" not in entry:
            raise ValueError(f"Missing bridge weights for {name}")
        bridges[name] = entry
    if not deltas:
        raise ValueError("No NAR LoRA tensors found in the checkpoint")
    return deltas, bridges


def _module(model, base):
    return model.get_submodule("model." + base)


def merge_nar_lora(model, path, scale=1.0):
    """Fold the deltas into the resident model (W += scale * B @ A) and swap bridges."""
    deltas, bridges = load_nar_lora(path)
    merged = 0
    with torch.no_grad():
        for base, a, b in deltas:
            module = _module(model, base)
            delta = (scale * (b @ a)).to(device=module.weight.device, dtype=module.weight.dtype)
            module.weight.add_(delta)
            merged += 1
        for name, entry in bridges.items():
            module = getattr(model, name)
            module.weight.copy_(entry["weight"].to(device=module.weight.device, dtype=module.weight.dtype))
            module.bias.copy_(entry["bias"].to(device=module.bias.device, dtype=module.bias.dtype))
    return merged


def snapshot_weights(model, path):
    """Clone every weight the pack mutates so restore is bit-exact."""
    deltas, _ = load_nar_lora(path)
    snap = []
    with torch.no_grad():
        for base, _, _ in deltas:
            weight = _module(model, base).weight
            snap.append((weight, weight.detach().clone()))
        for name in BRIDGES:
            module = getattr(model, name)
            snap.append((module.weight, module.weight.detach().clone()))
            snap.append((module.bias, module.bias.detach().clone()))
    return snap


def restore_weights(snapshot):
    with torch.no_grad():
        for tensor, saved in snapshot:
            tensor.copy_(saved)


def build_semantic(pipe, codes, style="", lyrics=""):
    """Wrap extracted codes in the plan/semantic containers the NAR expects."""
    from .pipeline import SemanticResult, SymbolicPlan
    from .protocol import SongRequest, token_prefixes
    request = SongRequest(style=style or "", lyrics=lyrics or "", cot="off", seed=1,
                          id="realaudio")
    prefix = token_prefixes(request, pipe.tokenizer, [])
    plan = SymbolicPlan(request=request, abc=None, abc_ids=[], prefix=prefix)
    tokens = [int(c) for c in np.asarray(codes).reshape(-1)]
    if not tokens:
        raise ValueError("The token file is empty")
    return SemanticResult(plan=plan, tokens=tokens, timing={}, truncated=False)


def render_tokens(pipe, codes, style="", lyrics=""):
    """Synthesize + decode the given codes (NAR LoRA state as-is)."""
    semantic = build_semantic(pipe, codes, style=style, lyrics=lyrics)
    latents = pipe.synthesize(semantic)
    audio = pipe.decode(latents)
    return audio, latents


@contextlib.contextmanager
def nar_lora_applied(pipe, path):
    """Fold the pack for the duration of the block, then restore bit-exactly.

    Snapshot cost is the full set of touched weights (28 layers x 6 linears,
    ~2.8 GB in fp16); the restore is a plain copy back.
    """
    model = pipe._load_model(for_nar=True)
    snapshot = snapshot_weights(model, path)
    try:
        merge_nar_lora(model, path)
        yield model
    finally:
        restore_weights(snapshot)
