"""Merge kohya-style LoRA adapters into YuE2 model weights (inference only)."""
from __future__ import annotations


def apply_lora(model, path):
    """Merge a LoRA (…lora_down/lora_up pairs, optional .alpha) into the model weights."""
    import torch
    from safetensors.torch import load_file
    state = load_file(str(path), device="cpu")
    pairs = {}
    for key, value in state.items():
        for suffix, slot in ((".lora_down.weight", "down"), (".lora_up.weight", "up"), (".alpha", "alpha")):
            if key.endswith(suffix):
                pairs.setdefault(key[: -len(suffix)], {})[slot] = value
                break
    merged, skipped = 0, 0
    for base, ab in pairs.items():
        if "down" not in ab or "up" not in ab:
            continue
        try:
            module = model.get_submodule(base)
        except AttributeError:
            skipped += 1
            continue
        down, up = ab["down"].float(), ab["up"].float()
        alpha = float(ab["alpha"]) if "alpha" in ab else down.shape[0]
        delta = (up @ down) * (alpha / down.shape[0])
        weight = module.weight
        with torch.no_grad():
            delta = delta.to(weight.device)
            module.weight.data = (weight.data.float() + delta).to(weight.dtype)
        merged += 1
    if not merged:
        raise RuntimeError(f"No LoRA weight pairs found in {path.name}")
    return {"lora": path.parent.name, "merged": merged, "skipped": skipped}
