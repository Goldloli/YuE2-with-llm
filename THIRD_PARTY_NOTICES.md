# Third-party code notices

The Oobleck VAE and SnakeBeta implementation in `modeling_vae.py` is derived
from stable-audio-tools commit `a6ae0cdf8b2eb1567a4b42ceadddec3712d99d45`.
The module hierarchy, weight normalization and activation equations preserve
the checkpoint's original inference implementation.

- Oobleck / stable-audio-tools: Copyright (c) 2023 Stability AI, MIT.
  Full text: `licenses/stable-audio-tools-MIT.txt`.
- SnakeBeta / BigVGAN: Copyright (c) 2022 NVIDIA CORPORATION, MIT.
  Full text: `licenses/SnakeBeta-NVIDIA-MIT.txt`.

These notices cover the identified source code and retain its original licenses.
The YuE2 model checkpoint weights are separately licensed under CC BY-NC 4.0,
with additional permission for individual creators; see MODEL_LICENSE for
academic-use terms, scope and full terms. This does not relicense third-party code.

## Ported implementation notices

The Windows CUDA acceleration kit (`web/cuda_kit.py`, `packaging/build_cuda_kit.py`,
`packaging/cuda-requirements-win.txt`) is ported from the open-source ASRbox project
(<https://github.com/Goldloli/asrbox>, MIT License, Copyright (c) 2026 Goldloli) and
adapted for YuE2 (paths, state model, manifest schema). The original MIT license
text is reproduced in `licenses/ASRbox-MIT.txt`.

## Web assets

- **Inter Tight** (Google Fonts) — SIL Open Font License, Version 1.1.
  Full text: `web/static/vendor/intertight/OFL.txt`.
- **Phosphor Icons** — MIT License, Copyright (c) 2023 Phosphor Icons.
  Full text: `web/static/vendor/phosphor/LICENSE.txt`.
