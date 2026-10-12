"""Real-audio pack: LoRA fold/snapshot math and tokenizer head loading."""
import importlib.util
from pathlib import Path

import pytest
import torch
from safetensors.torch import save_file

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "models" / "YuE2-Realaudio" / "nar_lora_joint_v9.bf16.safetensors"
HEAD = ROOT / "models" / "YuE2-Realaudio" / "tokenizer_head_joint_v9.bf16.safetensors"

pytestmark = pytest.mark.skipif(not PACK.exists() or not HEAD.exists(),
                                reason="YuE2-Realaudio pack is not installed")


class ToyLayer(torch.nn.Module):
    def __init__(self, hidden=8):
        super().__init__()
        self.nar_self_attn = torch.nn.Module()
        for name in ("q_proj", "k_proj", "v_proj", "o_proj"):
            setattr(self.nar_self_attn, name, torch.nn.Linear(hidden, hidden, bias=False))
        self.nar_mlp = torch.nn.Module()
        for name in ("gate_proj", "up_proj", "down_proj"):
            setattr(self.nar_mlp, name, torch.nn.Linear(hidden, hidden, bias=False))


class ToyModel(torch.nn.Module):
    """Mirrors the attribute paths the pack targets: model.layers[i].nar_* + bridges."""

    def __init__(self, layers=2, hidden=8, latent=4):
        super().__init__()
        self.model = torch.nn.Module()
        self.model.layers = torch.nn.ModuleList([ToyLayer(hidden) for _ in range(layers)])
        self.vae2llm = torch.nn.Linear(latent, hidden)
        self.llm2vae = torch.nn.Linear(hidden, latent)


def tiny_pack(tmp_path, layers=2, hidden=8, rank=2, latent=4, seed=0):
    torch.manual_seed(seed)
    tensors = {}
    for i in range(layers):
        for mod in ("q_proj", "k_proj", "v_proj", "o_proj"):
            base = f"layers.{i}.nar_self_attn.{mod}"
            tensors[base + ".lora_A"] = torch.randn(rank, hidden, dtype=torch.float32)
            tensors[base + ".lora_B"] = torch.randn(hidden, rank, dtype=torch.float32)
        for mod in ("gate_proj", "up_proj", "down_proj"):
            base = f"layers.{i}.nar_mlp.{mod}"
            tensors[base + ".lora_A"] = torch.randn(rank, hidden, dtype=torch.float32)
            tensors[base + ".lora_B"] = torch.randn(hidden, rank, dtype=torch.float32)
    tensors["vae2llm.weight"] = torch.randn(hidden, latent)
    tensors["vae2llm.bias"] = torch.randn(hidden)
    tensors["llm2vae.weight"] = torch.randn(latent, hidden)
    tensors["llm2vae.bias"] = torch.randn(latent)
    path = tmp_path / "tiny_pack.safetensors"
    save_file(tensors, str(path))
    return path, tensors


def test_merge_math_and_bridge_replacement(tmp_path):
    from yue2.realaudio import load_nar_lora, merge_nar_lora
    path, tensors = tiny_pack(tmp_path)
    model = ToyModel()
    weight = model.model.layers[0].nar_self_attn.q_proj.weight.detach().clone()
    merge_nar_lora(model, path)
    a = tensors["layers.0.nar_self_attn.q_proj.lora_A"]
    b = tensors["layers.0.nar_self_attn.q_proj.lora_B"]
    expected = weight + b @ a
    assert torch.allclose(model.model.layers[0].nar_self_attn.q_proj.weight, expected)
    deltas, bridges = load_nar_lora(path)
    assert len(deltas) == 14  # 2 layers x 7 modules
    assert torch.equal(model.vae2llm.weight, bridges["vae2llm"]["weight"])
    assert torch.equal(model.llm2vae.bias, bridges["llm2vae"]["bias"])


def test_snapshot_restore_is_bit_exact(tmp_path):
    from yue2.realaudio import merge_nar_lora, restore_weights, snapshot_weights
    path, _ = tiny_pack(tmp_path, seed=1)
    model = ToyModel()
    before = {name: param.detach().clone() for name, param in model.named_parameters()}
    snapshot = snapshot_weights(model, path)
    merge_nar_lora(model, path)
    changed = [name for name, param in model.named_parameters()
               if not torch.equal(param, before[name])]
    assert changed, "merge should change weights"
    restore_weights(snapshot)
    for name, param in model.named_parameters():
        assert torch.equal(param, before[name]), f"{name} not restored bit-exactly"


def test_load_nar_lora_rejects_missing_pairs(tmp_path):
    from yue2.realaudio import load_nar_lora
    path = tmp_path / "broken.safetensors"
    save_file({"layers.0.nar_self_attn.q_proj.lora_A": torch.zeros(2, 4)}, str(path))
    with pytest.raises(ValueError):
        load_nar_lora(path)


def test_head_architecture_loads_the_published_checkpoint():
    spec = importlib.util.spec_from_file_location("realaudio_encode", ROOT / "tools" / "realaudio_encode.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    head = module.load_head(HEAD, "cpu")
    params = {name for name, _ in head.named_parameters()}
    assert len(params) == 103  # inp(2) + pos(1) + 8 layers x 12 + norm(2) + head(2)
    assert head.pos.shape == (1, 512, 512)


def test_tokenize_windows_and_trims_tail():
    spec = importlib.util.spec_from_file_location("realaudio_encode", ROOT / "tools" / "realaudio_encode.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seen = []

    class ToyHead(torch.nn.Module):
        def forward(self, x):
            seen.append(x.shape[1])
            return torch.zeros(x.shape[0], x.shape[1], module.VOCAB)

    frames = 1200  # 2 full windows + 176 padded
    codes = module.tokenize(ToyHead(), torch.zeros(frames, 1024), "cpu")
    assert seen == [512, 512, 512]
    assert codes.shape == (frames,)
    assert codes.dtype.name == "int32"
