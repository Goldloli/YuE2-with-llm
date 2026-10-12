"""Verify the MPS causal-attention patch against a CPU FP32 reference.

Reproduces the methodology of upstream issue #176: compare multi-token
prefill attention outputs on MPS BF16 with an explicit bool mask against
a CPU FP32 reference built from the same Q/K/V.
"""
import torch

from yue2.modeling_yue2 import sdpa

torch.manual_seed(0)
T, Hq, Hk, D = 705, 32, 8, 128  # heads with grouped-query attention
q = torch.randn(1, Hq, T, D)
k = torch.randn(1, Hk, T, D)
v = torch.randn(1, Hk, T, D)

ref = sdpa(q.clone(), k.clone(), v.clone(), is_causal=True).float().cpu()

print(f"mps available: {torch.backends.mps.is_available()}")
assert torch.backends.mps.is_available(), "MPS device not available"

q_mps = q.to("mps", torch.bfloat16)
k_mps = k.to("mps", torch.bfloat16)
v_mps = v.to("mps", torch.bfloat16)
out = sdpa(q_mps, k_mps, v_mps, is_causal=True).float().cpu()

max_abs = (out - ref).abs().max().item()
mean_abs = (out - ref).abs().mean().item()
print(f"max |mps - cpu_ref| = {max_abs:.6f}")
print(f"mean |mps - cpu_ref| = {mean_abs:.6f}")

# BF16 rounding alone should keep max error far below the ~0.3+ produced by
# the leaky is_causal=True fast path on MPS (issue #176 measured 0.32-0.57).
assert max_abs < 0.05, f"attention output deviates from reference: {max_abs}"

# Leak check: perturbing a future key/value must not change earlier outputs.
v2 = v_mps.clone()
v2[:, :, T - 1] += 1.0
out2 = sdpa(q_mps, k_mps, v2, is_causal=True).float().cpu()
leak = (out2[:, :, : T - 1] - out[:, :, : T - 1]).abs().max().item()
print(f"future-leak max delta = {leak:.6e}")
assert leak == 0.0, "causal mask leaks future information"

print("OK: patched MPS attention matches the CPU reference and is causal")
