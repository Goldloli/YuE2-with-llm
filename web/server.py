"""FastAPI backend for YuE2 Studio, a modern music-workstation interface for YuE2.

Serves the static frontend, a library persisted to web/data/library.json, and a
single-worker queue that drives YuE2Pipeline (plan -> semantic -> synthesize ->
decode) plus SheetSage2 audio transcriptions in a separate subprocess env.

Capability map (mirrors what YuE2 0.1.6 actually supports):
- Create:   text style + lyrics -> song (cot full/melody/off, instrumental)
- Cover:    keep an existing melody score, render in a new style (cot=melody
            strips chords, cot=full keeps harmony)
- Edit:     change style/lyrics/score -> new render (new generation, the
            original waveform is not preserved)
- Upload:   SheetSage2 transcribes an audio file to a melody score, which then
            feeds Cover. There is no direct audio conditioning, no extend /
            inpainting in YuE2 itself.
"""
from __future__ import annotations

import ipaddress
import json
import os
import queue
import random
import re
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
WEB = Path(__file__).resolve().parent
DATA = WEB / "data"
UPLOADS = DATA / "uploads"
OUTPUTS = ROOT / "outputs"
LIBRARY_FILE = DATA / "library.json"
ABC_TOOLS = ROOT / "skills" / "yue2-music" / "scripts"

# Windows-only CUDA acceleration kit (optional; downloaded from its own release).
# The injection has to happen before anything imports torch (torch is imported
# lazily further down), so the kit's torch tree wins over the bundled CPU build.
sys.path.insert(0, str(WEB))
try:
    import cuda_kit
except Exception as _cuda_kit_error:  # pragma: no cover - defensive
    cuda_kit = None
    print(f"CUDA kit module unavailable: {_cuda_kit_error}", file=sys.stderr)
else:
    try:
        cuda_kit.maybe_inject()
    except Exception as _cuda_kit_error:  # pragma: no cover - defensive
        print(f"CUDA kit injection skipped: {_cuda_kit_error}", file=sys.stderr)

MODEL_DIR = ROOT / "models" / "YuE2-3B"
VAE_DIR = ROOT / "models" / "YuE2-Vae"
VAE_LEGACY_DIR = ROOT / "models" / "YuE2-Vae-legacy"
LORAS_DIR = ROOT / "models" / "loras"
MLX_DIR = ROOT / "models" / "YuE2-3B-MLX"
MLX_PY = ROOT / ".venv-mlx" / "bin" / "python"
MLX_SCRIPT = ROOT / "tools" / "mlx_generate.py"

# Self-contained one-click package: portable runtime + preinstalled envs. When
# present these replace the developer venvs for the optional subprocesses.
BUNDLED_RUNTIME = ROOT / "runtime" / ("python.exe" if os.name == "nt" else "bin/python3")
BUNDLED_WEB_ENV = ROOT / "envs" / "web"
BUNDLED_MLX_ENV = ROOT / "envs" / "mlx"


def bundled_ready() -> bool:
    return BUNDLED_RUNTIME.exists() and (BUNDLED_WEB_ENV / "torch").is_dir()


def mlx_interpreter() -> tuple[Path | None, dict]:
    """Interpreter + extra env for the MLX subprocess (bundled env or dev venv)."""
    if bundled_ready() and (BUNDLED_MLX_ENV / "mlx").is_dir():
        return BUNDLED_RUNTIME, {"PYTHONPATH": str(BUNDLED_MLX_ENV)}
    if MLX_PY.exists():
        return MLX_PY, {}
    return None, {}


def sheetsage_interpreter() -> tuple[Path | None, dict]:
    """Interpreter + extra env for the transcription / encode subprocesses."""
    if bundled_ready() and (BUNDLED_WEB_ENV / "torchaudio").is_dir():
        return BUNDLED_RUNTIME, {"PYTHONPATH": str(BUNDLED_WEB_ENV)}
    if SHEETSAGE_PY.exists():
        return SHEETSAGE_PY, {}
    return None, {}


def subprocess_env(extra: dict) -> dict:
    env = dict(os.environ)
    env.update(extra)
    return env
VAE_MERGE_DIR = ROOT / "models" / "YuE2-Vae-merge"
REAUDIO_DIR = ROOT / "models" / "YuE2-Realaudio"
REAUDIO_LORA = REAUDIO_DIR / "nar_lora_joint_v9.bf16.safetensors"
REAUDIO_ENCODE_SCRIPT = ROOT / "tools" / "realaudio_encode.py"

DOWNLOAD_ENDPOINTS = {"mirror": "https://hf-mirror.com", "huggingface": "https://huggingface.co"}

# Components shown in the model manager. `paths` are relative to models/ and
# drive both the installed check and the on-disk progress calculation.
MODEL_COMPONENTS = [
    {"id": "core", "group": "core", "label": "YuE2-3B + YuE2-Vae", "mode": "core",
     "bytes": 7795000000, "required": True, "platform": None,
     "paths": ["YuE2-3B/model.safetensors", "YuE2-Vae/model.safetensors"]},
    {"id": "decoders", "group": "decoders", "label": "Vae-legacy + Merge 0.666", "mode": "decoders",
     "bytes": 1063000000, "required": False, "platform": None,
     "paths": ["YuE2-Vae-legacy/model.safetensors", "YuE2-Vae-merge/model.safetensors"]},
    {"id": "realaudio", "group": "extras", "label": "Realaudio toolkit", "mode": "realaudio",
     "bytes": 164991312, "required": False, "platform": None,
     "paths": ["YuE2-Realaudio/tokenizer_head_joint_v9.bf16.safetensors",
               "YuE2-Realaudio/nar_lora_joint_v9.bf16.safetensors",
               "YuE2-Realaudio/assets/sem_nbr_idx.npy",
               "YuE2-Realaudio/assets/sem_nbr_cos.npy"]},
    {"id": "lora-deathmetal-v1", "group": "lora", "label": "Death Metal v1", "mode": "lora-deathmetal",
     "bytes": 278968264, "required": False, "platform": None,
     "paths": ["loras/deathmetal-v1/lora.safetensors"]},
    {"id": "lora-jpop-t4", "group": "lora", "label": "J-Pop T4", "mode": "lora-jpop",
     "bytes": 106474864, "required": False, "platform": None,
     "paths": ["loras/jpop-t4/lora.safetensors"]},
    {"id": "lora-instrumental-v3abc", "group": "lora", "label": "Instrumental v3 (ABC)",
     "mode": "lora-instrumental", "bytes": 278962592, "required": False, "platform": None,
     "paths": ["loras/instrumental-v3abc/lora.safetensors"]},
    {"id": "transcribe", "group": "transcribe", "label": "SheetSage2 + MERT-v2-FullSong",
     "mode": "transcribe", "bytes": 2700000000, "required": False, "platform": None,
     "paths": ["SheetSage2/model.safetensors", "SheetSage2/config.json",
               "MERT-v2-FullSong/config.json", "MERT-v2-FullSong/model.safetensors"]},
    {"id": "mlx-8bit", "group": "mlx", "label": "MLX · 8-bit", "mode": "mlx-8bit",
     "bytes": 4529929856, "required": False, "platform": "darwin",
     "paths": ["YuE2-3B-MLX/8bit/model.safetensors", "YuE2-3B-MLX/8bit/vae.safetensors"]},
    {"id": "mlx-bf16", "group": "mlx", "label": "MLX · bf16", "mode": "mlx-bf16",
     "bytes": 7526883400, "required": False, "platform": "darwin",
     "paths": ["YuE2-3B-MLX/bf16/model.safetensors", "YuE2-3B-MLX/bf16/vae.safetensors"]},
    {"id": "mlx-4bit", "group": "mlx", "label": "MLX · 4-bit", "mode": "mlx-4bit",
     "bytes": 3636149612, "required": False, "platform": "darwin",
     "paths": ["YuE2-3B-MLX/4bit/model.safetensors", "YuE2-3B-MLX/4bit/vae.safetensors"]},
    # Windows-only acceleration kit: a cu128 torch tree published as its own
    # split release. Never shipped in the package; downloaded from the app.
    {"id": "cuda-kit", "group": "cuda", "label": "CUDA 加速套件（NVIDIA GPU）",
     "mode": "cuda-kit", "bytes": 0, "required": False, "platform": "win32",
     "paths": []},
]
MODEL_COMPONENTS_BY_ID = {c["id"]: c for c in MODEL_COMPONENTS}


def core_installed() -> bool:
    """True when the required core model files are on disk (UI first-run gate)."""
    core = MODEL_COMPONENTS_BY_ID["core"]
    return all((ROOT / "models" / rel).exists() for rel in core["paths"])


SETTINGS_FILE = DATA / "settings.json"
SHEETSAGE_PY = ROOT / ".venv-sheetsage2" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
SHEETSAGE_MODEL = ROOT / "models" / "SheetSage2"
MERT_MODEL = ROOT / "models" / "MERT-v2-FullSong"
TRANSCRIBE_SCRIPT = ABC_TOOLS / "transcribe.py"

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".opus", ".wma"}
AUDIO_MIME = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac",
              ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".aac": "audio/aac",
              ".opus": "audio/opus", ".wma": "audio/x-ms-wma"}

STAGES = ["planning", "composing", "synthesizing", "decoding"]


def transcribe_available():
    interpreter, _ = sheetsage_interpreter()
    return (interpreter is not None and (SHEETSAGE_MODEL / "config.json").exists()
            and (MERT_MODEL / "config.json").exists() and TRANSCRIBE_SCRIPT.exists())


def mlx_variants():
    """Installed MLX variant names (dirs that carry weights), e.g. ['8bit', 'bf16']."""
    if not MLX_DIR.exists():
        return []
    return sorted(p.parent.name for p in MLX_DIR.glob("*/model.safetensors"))


def mlx_variant_effective():
    """The configured variant when installed, otherwise the first installed one."""
    installed = mlx_variants()
    configured = settings.get("mlx_variant")
    if configured in installed:
        return configured
    return installed[0] if installed else configured


def mlx_available():
    interpreter, _ = mlx_interpreter()
    return (interpreter is not None and MLX_SCRIPT.exists()
            and bool(mlx_variants()))


def decoder_vae_path(decoder):
    """Map the decoder setting to an alternate VAE dir; None means the bundled default."""
    if decoder == "legacy" and (VAE_LEGACY_DIR / "model.safetensors").exists():
        return str(VAE_LEGACY_DIR)
    if decoder == "merge" and (VAE_MERGE_DIR / "model.safetensors").exists():
        return str(VAE_MERGE_DIR)
    return None


def default_backend_effective():
    """The configured default inference backend, downgraded when MLX is unavailable."""
    backend = settings.get("default_backend") or "torch"
    if backend == "mlx" and not mlx_available():
        return "torch"
    return backend


def vllm_available():
    import importlib.util
    try:
        return importlib.util.find_spec("vllm") is not None
    except (ImportError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Library store

class Library:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.songs = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            for song in json.loads(self.path.read_text(encoding="utf-8")):
                song.setdefault("kind", "song")
                self.songs[song["id"]] = song
        self._seed_from_outputs()

    def _seed_from_outputs(self):
        if not OUTPUTS.exists():
            return
        changed = False
        for folder in sorted(OUTPUTS.iterdir()):
            result_file = folder / "result.json"
            request_file = folder / "request.json"
            if folder.name in self.songs or not result_file.exists() or not request_file.exists():
                continue
            try:
                result = json.loads(result_file.read_text(encoding="utf-8"))
                request = json.loads(request_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if result.get("status") != "complete" or not (folder / "audio.flac").exists():
                continue
            self.songs[folder.name] = {
                "id": folder.name, "kind": "song",
                "title": folder.name.replace("_", " ").replace("-", " ").title(),
                "style": request.get("style", ""), "lyrics": request.get("lyrics", ""),
                "cot": request.get("cot", "full"), "seed": request.get("seed"),
                "cfg_scale": request.get("cfg_scale"),
                "instrumental": request.get("lyrics", "") == "[Instrumental]",
                "status": "complete", "stage": None, "progress": {}, "error": None,
                "created_at": folder.stat().st_mtime,
                "audio_seconds": result.get("audio_seconds"),
                "has_score": (folder / "score.abc").exists(),
                "truncated": result.get("truncated"), "parent_id": None,
            }
            changed = True
        if changed:
            self._flush()

    def _flush(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.list(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def list(self):
        return sorted(self.songs.values(), key=lambda s: s.get("created_at", 0), reverse=True)

    def get(self, song_id):
        song = self.songs.get(song_id)
        if song is None:
            raise KeyError(song_id)
        return song

    def put(self, song):
        with self.lock:
            self.songs[song["id"]] = song
            self._flush()

    def update(self, song_id, **fields):
        with self.lock:
            song = self.songs[song_id]
            song.update(fields)
            self._flush()
            return dict(song)

    def delete(self, song_id):
        with self.lock:
            self.songs.pop(song_id, None)
            self._flush()


library = Library(LIBRARY_FILE)

# Jobs that were queued or running when the previous process died cannot make
# progress; surface them as interrupted instead of leaving the UI stuck on them.
_orphaned = [s for s in library.songs.values() if s.get("status") in {"queued", "running"}]
if _orphaned:
    for _stale in _orphaned:
        _stale.update({"status": "failed", "stage": None, "progress": {},
                       "error": "Interrupted by a server restart"})
    library._flush()


# ---------------------------------------------------------------------------
# Runtime settings (persisted): audio decoder selection

DEFAULT_SETTINGS = {"decoder": "default", "backend": "torch", "quantization": "none",
                    "offload_ar": False, "budget": 24.0, "style_language": "auto",
                    "default_backend": "mlx", "default_mode": "simple",
                    "default_max_seconds": None, "default_cfg": None,
                    "autoplay_on_complete": False, "notify_on_complete": False,
                    "poll_interval": 1.5, "mlx_variant": "8bit",
                    "start_view": "create", "default_sort": "new", "reduce_motion": False,
                    "download_source": "mirror", "default_lora": None,
                    "llm_base_url": "", "llm_model": "", "llm_api_key": "",
                    "llm_timeout": 10.0, "llm_enhance_output": "zh",
                    "llm_providers": [], "llm_active_provider": None}


class Settings:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.data = dict(DEFAULT_SETTINGS)
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                self.data.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
            except (ValueError, OSError):
                pass

    def get(self, key):
        return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def update(self, **fields):
        with self.lock:
            self.data.update({k: v for k, v in fields.items() if k in DEFAULT_SETTINGS})
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        return dict(self.data)


settings = Settings(SETTINGS_FILE)


# ---------------------------------------------------------------------------
# LoRA adapters (style fine-tunes of the base model, merged at load time)

LORA_LABELS = {
    "deathmetal-v1": "Death Metal v1",
    "jpop-t4": "J-Pop T4",
    "instrumental-v3abc": "Instrumental v3 (ABC)",
}


def lora_path(lora_id):
    return LORAS_DIR / lora_id / "lora.safetensors"


def list_loras():
    found = []
    if LORAS_DIR.is_dir():
        for d in sorted(LORAS_DIR.iterdir()):
            if not d.is_dir() or not (d / "lora.safetensors").exists():
                continue
            info = {"id": d.name, "label": LORA_LABELS.get(d.name, d.name)}
            try:
                from safetensors import safe_open
                with safe_open(str(d / "lora.safetensors"), framework="pt") as f:
                    meta = f.metadata() or {}
                info["rank"] = meta.get("rank")
                info["branch"] = meta.get("branch")
            except Exception:
                pass
            found.append(info)
    return found


def apply_lora(model, path):
    from lora import apply_lora as _apply
    return _apply(model, path)


# ---------------------------------------------------------------------------
# Model downloads (independent single-concurrency channel; never blocks jobs)


def _path_bytes(path: Path) -> int:
    """Bytes already on disk for one target file, including its .parts chunks."""
    total = 0
    if path.exists():
        total += path.stat().st_size
    parts = path.parent / (path.name + ".parts")
    if parts.is_dir():
        for chunk in parts.iterdir():
            try:
                total += chunk.stat().st_size
            except OSError:
                pass
    return total


def _component_bytes(component) -> int:
    return sum(_path_bytes(ROOT / "models" / rel) for rel in component["paths"])


class DownloadManager:
    """Runs one `tools/hf_download.py` subprocess at a time, in parallel with jobs."""

    def __init__(self):
        self.lock = threading.Lock()
        self.current = None  # {"component", "mode", "source", "proc", "error", "cancelled"}

    def snapshot(self):
        with self.lock:
            if self.current is None:
                return None
            proc = self.current["proc"]
            running = proc is not None and proc.poll() is None
            return {"component": self.current["component"], "source": self.current["source"],
                    "error": self.current["error"], "started": self.current["started"],
                    "running": running}

    def start(self, component, source):
        with self.lock:
            if self.current is not None:
                if self.current["proc"] is not None and self.current["proc"].poll() is None:
                    raise HTTPException(409, f"A download is already running ({self.current['component']})")
                self.current = None  # clear a finished/failed entry so retries work
            env = dict(os.environ)
            env["YUE2_HF_ENDPOINT"] = DOWNLOAD_ENDPOINTS[source]
            proc = subprocess.Popen(
                [sys.executable, "-B", str(ROOT / "tools" / "hf_download.py"), component["mode"]],
                cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace")
            self.current = {"component": component["id"], "mode": component["mode"],
                            "source": source, "proc": proc, "error": None, "cancelled": False,
                            "started": time.time(), "log_tail": []}
            threading.Thread(target=self._watch, args=(proc,), daemon=True,
                             name="yue2-download").start()

    def _watch(self, proc):
        for line in proc.stdout:
            with self.lock:
                if self.current is not None:
                    self.current["log_tail"].append(line.rstrip())
                    del self.current["log_tail"][:-12]
        code = proc.wait()
        with self.lock:
            if self.current is not None:
                if self.current["cancelled"]:
                    self.current = None
                elif code != 0:
                    tail = " | ".join(x for x in self.current["log_tail"][-3:] if x)
                    self.current["error"] = tail or f"exit code {code}"
                    # keep the error visible until the next start / cancel
                    self.current["proc"] = None

    def cancel(self, component_id):
        with self.lock:
            if self.current is None or self.current["component"] != component_id:
                raise HTTPException(404, "No download is running for that component")
            self.current["cancelled"] = True
            proc = self.current["proc"]
            if proc is not None and proc.poll() is None:
                proc.terminate()
            else:
                self.current = None
        return True


downloads = DownloadManager()


# ---------------------------------------------------------------------------
# Job runner (single worker: the torch pipeline is not concurrent-safe, and
# transcription shares the same memory budget)

class Runner:
    def __init__(self):
        self.jobs = queue.Queue()
        self.pipe = None
        self.pipe_error = None
        self.loading = False
        self.cancel_flags = {}
        self.procs = {}
        self.current_id = None
        self.loaded_lora = None      # adapter merged into the resident model
        self.lora_merge = None       # merge report for the active run
        threading.Thread(target=self._loop, daemon=True, name="yue2-runner").start()

    def device_name(self):
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            if torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"

    def model_status(self):
        if self.pipe is not None:
            return "ready"
        if self.pipe_error is not None:
            return "failed"
        if self.loading:
            return "loading"
        return "cold"

    def submit(self, kind, item_id, kwargs=None):
        self.cancel_flags[item_id] = threading.Event()
        self.jobs.put((kind, item_id, kwargs or {}))

    def cancel(self, item_id):
        flag = self.cancel_flags.get(item_id)
        if flag is not None:
            flag.set()
        proc = self.procs.get(item_id)
        if proc is not None and proc.poll() is None:
            proc.terminate()

    def _loop(self):
        while True:
            kind, item_id, kwargs = self.jobs.get()
            self.current_id = item_id
            try:
                if kind == "transcribe":
                    self._transcribe(item_id)
                elif kind == "generate_mlx":
                    self._generate_mlx(item_id, kwargs)
                elif kind == "redecode":
                    self._redecode(item_id, kwargs)
                elif kind == "rebuild":
                    self._rebuild(item_id, kwargs)
                else:
                    self._generate(item_id, kwargs)
            except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
                traceback.print_exc()
                cancelled = isinstance(exc, InterruptedError)
                try:
                    library.update(item_id, status="cancelled" if cancelled else "failed",
                                   stage=None, error=None if cancelled else f"{type(exc).__name__}: {exc}")
                except KeyError:
                    pass
            finally:
                self.current_id = None
                self.cancel_flags.pop(item_id, None)
                self.procs.pop(item_id, None)

    # ----- SheetSage2 transcription (separate pinned env, subprocess) -----

    def _transcribe(self, item_id):
        if self.cancel_flags[item_id].is_set():
            raise InterruptedError("Cancelled while queued")
        if not transcribe_available():
            raise RuntimeError("SheetSage2 environment is not installed on this machine")
        folder = UPLOADS / item_id
        sources = [p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXTS and p.is_file()]
        if not sources:
            raise FileNotFoundError("Uploaded audio is missing")
        out = folder / "transcription"
        device = "cuda" if self.device_name() == "cuda" else "cpu"
        sheetsage_py, sheetsage_env = sheetsage_interpreter()
        cmd = [str(sheetsage_py), str(TRANSCRIBE_SCRIPT), str(sources[0]),
               "--output", str(out), "--task", "melody-full",
               "--model", str(SHEETSAGE_MODEL), "--base-model", str(MERT_MODEL),
               "--device", device, "--dtype", "bf16" if device == "cuda" else "fp32",
               "--offline"]
        library.update(item_id, status="running", stage="transcribing")
        proc = subprocess.Popen(cmd, cwd=str(ABC_TOOLS), env=subprocess_env(sheetsage_env),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
        self.procs[item_id] = proc
        log_tail = []
        for line in proc.stdout:
            log_tail.append(line.rstrip())
            del log_tail[:-40]
            if self.cancel_flags[item_id].is_set():
                proc.terminate()
        code = proc.wait()
        if self.cancel_flags[item_id].is_set():
            raise InterruptedError("Transcription cancelled")
        score = out / "score.abc"
        if code != 0 or not score.exists():
            detail = "\n".join(log_tail[-8:]) or f"exit code {code}"
            raise RuntimeError(f"Transcription failed: {detail}")
        library.update(item_id, status="complete", stage=None, has_score=True,
                       progress={}, error=None)

    # ----- YuE2 generation -----

    def _load_pipe(self):
        from yue2 import YuE2Pipeline
        model = str(MODEL_DIR) if MODEL_DIR.exists() else "m-a-p/YuE2-3B"
        vae = str(VAE_DIR) if VAE_DIR.exists() else "m-a-p/YuE2-Vae"
        backend = settings.get("backend")
        if backend == "vllm" and not vllm_available():
            backend = "torch"
        quantization = settings.get("quantization")
        if quantization == "fp8" and self.device_name() != "cuda":
            quantization = "none"
        self.loading = True
        try:
            self.pipe = YuE2Pipeline.from_pretrained(
                model, vae=vae, device="auto",
                backend=backend, quantization=quantization,
                offload_ar=bool(settings.get("offload_ar")),
                memory_budget_gib=float(settings.get("budget") or 24),
                local_files_only=MODEL_DIR.exists(), progress=False)
        finally:
            self.loading = False

    def reload_pipe(self):
        """Drop the resident pipeline so the next job picks up new load-time settings."""
        self._release_model()
        self.pipe = None
        self.pipe_error = None

    def _release_model(self):
        """Drop the resident weights so the next load can merge a different adapter."""
        if self.pipe is not None:
            self.pipe.close()
        try:
            import gc
            import torch
            gc.collect()
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        self.loaded_lora = None

    def _ensure_lora(self, lora):
        """Make the requested LoRA the one merged into the resident model."""
        if lora == self.loaded_lora and (lora is None or self.pipe._model is not None):
            return
        if self.pipe is not None and self.pipe._model is not None:
            self._release_model()
        if lora is None:
            self.loaded_lora = None
            self.lora_merge = None
            return
        path = lora_path(lora)
        if not path.exists():
            raise FileNotFoundError(f"LoRA adapter '{lora}' is not installed")
        self.lora_merge = apply_lora(self.pipe._load_model(), path)
        self.loaded_lora = lora

    def _generate(self, song_id, kwargs):
        cancel_event = self.cancel_flags[song_id]
        cancelled = cancel_event.is_set
        if cancelled():
            raise InterruptedError("Cancelled while queued")
        want_lora = kwargs.pop("lora", None)
        sampling_over = kwargs.pop("sampling", None) or {}
        plan_only = kwargs.pop("plan_only", False)
        instrumental = kwargs.pop("instrumental", False)
        decoder = settings.get("decoder")
        if decoder in {"legacy", "merge"} and decoder_vae_path(decoder) is None:
            decoder = "default"
        if self.pipe is None:
            library.update(song_id, status="running", stage="loading_model", progress={})
            try:
                self._load_pipe()
            except Exception as exc:
                self.pipe_error = f"{type(exc).__name__}: {exc}"
                raise
        if want_lora != self.loaded_lora:
            library.update(song_id, stage="loading_model")
        pipe = self.pipe
        self._ensure_lora(want_lora)

        from yue2.pipeline import SongResult
        from yue2.storage import identity

        library.update(song_id, status="running", stage="planning",
                       progress={"abc_tokens": 0, "semantic_tokens": 0})
        request = pipe._request(**kwargs)
        import dataclasses as _dc
        fields = dict(sampling_over)
        max_seconds = fields.pop("max_seconds", None)
        ode_steps = fields.pop("ode_steps", None)
        if max_seconds is not None:
            fields["max_tokens"] = min(int(max_seconds) * 25, 9000)
        semantic_sampling = None
        if fields:
            from yue2.protocol import Sampling
            semantic_sampling = _dc.replace(Sampling(), **fields)
        config = pipe.effective_config(request, semantic_sampling=semantic_sampling)
        config["lora"] = want_lora or None
        if want_lora:
            config["lora_merge"] = self.lora_merge
        if decoder in {"legacy", "merge"}:
            config["decoder_release"] = decoder
        if ode_steps is not None:
            config["ode_steps_override"] = int(ode_steps)
        config["plan_only"] = plan_only
        request_id = identity({"request": request.to_dict(), "config": config, "weights": pipe.weights})

        progress = {"abc_tokens": 0, "semantic_tokens": 0}

        def on_token(phase, _token):
            key = "abc_tokens" if phase == "abc" else "semantic_tokens"
            progress[key] += 1
            if progress[key] % 25 == 0:
                library.update(song_id, progress=dict(progress))

        start = time.perf_counter()
        plan = pipe.plan(request=request, cancelled=cancelled, on_token=on_token)
        if plan_only:
            out_dir = OUTPUTS / song_id
            out_dir.mkdir(parents=True, exist_ok=True)
            plan.save(out_dir)
            (out_dir / "result.json").write_text(json.dumps({
                "status": "complete", "plan_only": True, "audio_seconds": None,
                "identity": request_id, "timing": dict(plan.timing), "weights": pipe.weights,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            library.update(song_id, status="complete", stage=None, progress=dict(progress),
                           error=None, has_score=plan.abc is not None)
            return
        if instrumental and plan.abc:
            try:
                converted, check = instrumentalize_score(plan.abc)
            except Exception as exc:  # noqa: BLE001 - transfer failure must not block generation
                library.update(song_id, instrumental_warning=f"{type(exc).__name__}: {exc}")
            else:
                if check["vocal_notes_before"]:
                    out_dir = OUTPUTS / song_id
                    out_dir.mkdir(parents=True, exist_ok=True)
                    (out_dir / "score.model.abc").write_text(plan.abc, encoding="utf-8")
                    (out_dir / "transfer.json").write_text(json.dumps(check, ensure_ascii=False, indent=2),
                                                           encoding="utf-8")
                    request = _dc.replace(request, abc=converted)
                    request_id = identity({"request": request.to_dict(), "config": config,
                                           "weights": pipe.weights})
                    plan = pipe.plan(request=request, cancelled=cancelled)
        library.update(song_id, stage="composing", progress=dict(progress))
        semantic = pipe.generate_semantic(plan, sampling=semantic_sampling, cancelled=cancelled, on_token=on_token)
        library.update(song_id, stage="synthesizing", progress=dict(progress))
        nar_start = time.perf_counter()
        saved_config = None
        if ode_steps is not None:
            saved_config = pipe.generation_config
            pipe.generation_config = _dc.replace(saved_config, ode_steps=int(ode_steps))
        try:
            latents = pipe.synthesize(semantic, cancelled=cancelled)
        finally:
            if saved_config is not None:
                pipe.generation_config = saved_config
        nar_seconds = time.perf_counter() - nar_start
        if cancelled():
            raise InterruptedError("Cancelled before VAE")
        library.update(song_id, stage="decoding", progress=dict(progress))
        vae_start = time.perf_counter()
        audio = pipe.decode(latents, vae=decoder_vae_path(decoder))
        timing = {"abc": plan.timing, "semantic": semantic.timing, "nar_seconds": nar_seconds,
                  "vae_seconds": time.perf_counter() - vae_start, "load": dict(pipe.load_timing),
                  "e2e_seconds": time.perf_counter() - start}

        result = SongResult(audio, 48000, semantic, latents, config, pipe.weights, timing, request_id)
        out_dir = OUTPUTS / song_id
        out_dir.mkdir(parents=True, exist_ok=True)
        saved = result.save_artifacts(out_dir)
        library.update(song_id, status="complete", stage=None, progress=dict(progress),
                       error=None, audio_seconds=saved["audio_seconds"],
                       has_score=plan.abc is not None, truncated=saved["truncated"])

    # ----- MLX generation (Apple Silicon native backend, subprocess) -----

    def _generate_mlx(self, item_id, kwargs):
        if self.cancel_flags[item_id].is_set():
            raise InterruptedError("Cancelled while queued")
        if not mlx_available():
            raise RuntimeError("MLX backend is not installed (see tools/download_mlx.sh)")
        sampling_over = kwargs.pop("sampling", None) or {}
        plan_only = kwargs.pop("plan_only", False)
        instrumental = kwargs.pop("instrumental", False)
        folder = OUTPUTS / item_id
        folder.mkdir(parents=True, exist_ok=True)
        mlx_py, mlx_env = mlx_interpreter()
        cmd = [str(mlx_py), str(MLX_SCRIPT), "--model", str(MLX_DIR), "--variant", mlx_variant_effective(),
               "--style", kwargs["style"], "--lyrics", kwargs.get("lyrics", ""),
               "--cot", kwargs.get("cot", "full"), "--seed", str(kwargs["seed"]),
               "--style-language", kwargs.get("style_language", "auto"),
               "--out-dir", str(folder)]
        if kwargs.get("style_original") is not None:
            cmd += ["--style-original", kwargs["style_original"]]
        if sampling_over.get("temperature") is not None:
            cmd += ["--temperature", str(sampling_over["temperature"])]
        if sampling_over.get("top_p") is not None:
            cmd += ["--top-p", str(sampling_over["top_p"])]
        if sampling_over.get("top_k") is not None:
            cmd += ["--top-k", str(sampling_over["top_k"])]
        if sampling_over.get("max_seconds") is not None:
            cmd += ["--max-semantic-tokens", str(min(int(sampling_over["max_seconds"]) * 25, 9000))]
        if sampling_over.get("ode_steps") is not None:
            cmd += ["--steps", str(sampling_over["ode_steps"])]
        if plan_only:
            cmd += ["--plan-only"]
        if instrumental:
            cmd += ["--instrumental"]
        if kwargs.get("abc") is not None:
            abc_file = folder / "input.abc"
            abc_file.write_text(kwargs["abc"], encoding="utf-8")
            cmd += ["--abc-file", str(abc_file)]
        library.update(item_id, status="running", stage="loading_model",
                       progress={"abc_tokens": 0, "semantic_tokens": 0})
        proc = subprocess.Popen(cmd, cwd=str(ROOT), env=subprocess_env(mlx_env),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
        self.procs[item_id] = proc
        progress = {"abc_tokens": 0, "semantic_tokens": 0}
        log_tail = []
        for line in proc.stdout:
            line = line.rstrip()
            log_tail.append(line)
            del log_tail[:-24]
            try:
                event = json.loads(line)
            except ValueError:
                continue
            phase = event.get("phase")
            if phase == "planning":
                if event.get("tokens"):
                    progress["abc_tokens"] = event["tokens"]
                library.update(item_id, stage="planning", progress=dict(progress))
            elif phase == "composing":
                if event.get("tokens"):
                    progress["semantic_tokens"] = event["tokens"]
                library.update(item_id, stage="composing", progress=dict(progress))
            elif phase == "synthesizing":
                library.update(item_id, stage="synthesizing", progress=dict(progress))
            elif phase == "decoding":
                library.update(item_id, stage="decoding")
            elif phase == "error":
                self.procs.pop(item_id, None)
                proc.wait()
                raise RuntimeError(event.get("error") or "MLX generation failed")
            elif phase == "instrumental_fallback":
                library.update(item_id, instrumental_warning=event.get("error"))
            elif phase == "done":
                progress["semantic_tokens"] = event.get("semantic_tokens", progress["semantic_tokens"])
            elif "tokens" in event:  # planning token counters
                progress["abc_tokens"] = event["tokens"]
                library.update(item_id, stage="planning", progress=dict(progress))
        code = proc.wait()
        self.procs.pop(item_id, None)
        if self.cancel_flags[item_id].is_set():
            raise InterruptedError("Generation cancelled")
        result_file = folder / "result.json"
        if code != 0 or not result_file.exists():
            detail = "\n".join(log_tail[-6:]) or f"exit code {code}"
            raise RuntimeError(f"MLX generation failed: {detail}")
        saved = json.loads(result_file.read_text(encoding="utf-8"))
        library.update(item_id, status="complete", stage=None, progress=dict(progress),
                       error=None, audio_seconds=saved.get("audio_seconds"),
                       has_score=(folder / "score.abc").exists(), truncated=saved.get("truncated"))

    # ----- realaudio rebuild: encode an upload, fold the NAR LoRA, re-render -----

    def _rebuild(self, item_id, kwargs):
        if self.cancel_flags[item_id].is_set():
            raise InterruptedError("Cancelled while queued")
        source_id = kwargs["source_id"]
        source = library.get(source_id)
        folder = UPLOADS / source_id
        out_dir = OUTPUTS / item_id
        out_dir.mkdir(parents=True, exist_ok=True)
        tokens_path = folder / "realaudio" / "tokens.npy"
        cached = tokens_path.exists() and tokens_path.stat().st_mtime >= max(
            (p.stat().st_mtime for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXTS),
            default=tokens_path.stat().st_mtime)
        if not cached:
            sources = sorted(p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXTS)
            if not sources:
                raise FileNotFoundError("Uploaded audio is missing")
            device = "cuda" if self.device_name() == "cuda" else "cpu"
            sheetsage_py, sheetsage_env = sheetsage_interpreter()
            cmd = [str(sheetsage_py), str(REAUDIO_ENCODE_SCRIPT), str(sources[0]),
                   "--output", str(tokens_path), "--device", device]
            library.update(item_id, status="running", stage="encoding")
            proc = subprocess.Popen(cmd, cwd=str(ROOT), env=subprocess_env(sheetsage_env),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace")
            self.procs[item_id] = proc
            log_tail = []
            for line in proc.stdout:
                log_tail.append(line.rstrip())
                del log_tail[:-16]
                if self.cancel_flags[item_id].is_set():
                    proc.terminate()
            code = proc.wait()
            self.procs.pop(item_id, None)
            if self.cancel_flags[item_id].is_set():
                raise InterruptedError("Cancelled while encoding")
            if code != 0 or not tokens_path.exists():
                raise RuntimeError("Realaudio encode failed: "
                                   + (" | ".join(x for x in log_tail[-3:] if x) or f"exit code {code}"))

        import numpy as np
        codes = np.load(tokens_path)
        if self.pipe is None:
            library.update(item_id, status="running", stage="loading_model", progress={})
            self._load_pipe()
        decoder = settings.get("decoder")
        if decoder in {"legacy", "merge"} and decoder_vae_path(decoder) is None:
            decoder = "default"

        from yue2.realaudio import nar_lora_applied, build_semantic
        style = source.get("style") or ""
        lyrics = source.get("lyrics") or ""
        semantic = build_semantic(self.pipe, codes, style=style, lyrics=lyrics)
        library.update(item_id, status="running", stage="rebuilding",
                       progress={"frames": int(codes.size)})
        with nar_lora_applied(self.pipe, str(REAUDIO_LORA)):
            latents = self.pipe.synthesize(semantic, cancelled=self.cancel_flags[item_id].is_set)
        if self.cancel_flags[item_id].is_set():
            raise InterruptedError("Cancelled before VAE")
        library.update(item_id, stage="decoding")
        audio = self.pipe.decode(latents, vae=decoder_vae_path(decoder))

        import soundfile as sf
        sf.write(str(out_dir / "audio.flac"), audio, 48000, subtype="PCM_24")
        np.save(out_dir / "latent.npy", np.asarray(latents, dtype=np.float32))
        seconds = len(audio) / 48000
        frames = int(codes.size)
        (out_dir / "request.json").write_text(json.dumps({
            "style": style, "lyrics": lyrics, "cot": "off", "source": source_id,
            "frames": frames, "nar_lora": REAUDIO_LORA.name,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "result.json").write_text(json.dumps({
            "status": "complete", "backend": "torch", "sample_rate": 48000,
            "audio_seconds": seconds, "realaudio": {"frames": frames, "seconds": seconds},
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        library.update(item_id, status="complete", stage=None, progress={},
                       error=None, audio_seconds=seconds, has_score=False,
                       realaudio={"frames": frames, "seconds": round(seconds, 2)})

    # ----- re-decode a finished song with the other audio decoder -----

    def _redecode(self, item_id, kwargs):
        decoder = kwargs.get("decoder", "default")
        folder = OUTPUTS / item_id
        latents_path = folder / "latent.npy"
        if not latents_path.exists():
            raise FileNotFoundError("No saved latents for this item")
        import numpy as np
        latents = np.load(latents_path)
        if self.pipe is None:
            self._load_pipe()
        library.update(item_id, status="running", stage="decoding")
        audio = self.pipe.decode(latents, vae=decoder_vae_path(decoder))
        import soundfile as sf
        sf.write(str(folder / "audio.flac"), audio, 48000, subtype="PCM_24")
        config_file = folder / "config.json"
        if config_file.exists():
            try:
                config = json.loads(config_file.read_text(encoding="utf-8"))
                config["decoder_release"] = decoder if decoder in {"legacy", "merge"} else "standard"
                config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            except ValueError:
                pass
        library.update(item_id, status="complete", stage=None, error=None,
                       audio_seconds=len(audio) / 48000, decoder=decoder)


runner = Runner()


# ---------------------------------------------------------------------------
# Helpers

def slugify(title):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()[:60]
    return slug or "song"


def new_item_id(title):
    base = slugify(title)
    candidate = f"{base}-{int(time.time()) % 100000}"
    while candidate in library.songs or (OUTPUTS / candidate).exists() or (UPLOADS / candidate).exists():
        candidate = f"{base}-{random.randint(100000, 999999)}"
    return candidate


def public(song):
    return {k: v for k, v in song.items() if k != "lyrics"} | {"has_lyrics": bool(song.get("lyrics"))}


def get_item(song_id):
    try:
        return library.get(song_id)
    except KeyError:
        raise HTTPException(404, "Unknown item")


def item_folder(song):
    return (UPLOADS if song["kind"] == "upload" else OUTPUTS) / song["id"]


def current_score(song):
    """Return the best available ABC for this item (edited copy wins)."""
    folder = item_folder(song)
    for rel in ("edited_score.abc", "score.abc", "transcription/score.abc"):
        path = folder / rel
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None


def strip_abc_chords(abc):
    sys.path.insert(0, str(ABC_TOOLS))
    try:
        from abc_tools import strip_chords
        return strip_chords(abc)
    except Exception as exc:
        raise HTTPException(422, f"Could not strip chord symbols from the score: {exc}")


def abc_report(text):
    """Symbolic report for an ABC score (notes/meter/chords), via the skill tooling."""
    sys.path.insert(0, str(ABC_TOOLS))
    from abc_tools import parse, report, json_value
    data = report(parse(text))
    return json.loads(json.dumps(data, default=json_value))


def abc_compare(before, after):
    """Check sounding-note/meter invariants after editing a score."""
    sys.path.insert(0, str(ABC_TOOLS))
    from abc_tools import parse, compare, json_value, VOICES
    data = compare(parse(before), parse(after), VOICES)
    return json.loads(json.dumps(data, default=json_value))


INSTRUMENTAL_SCRIPTS = ROOT / "skills" / "yue2-music" / "instrumental" / "scripts"
TRANSFER_SNIPPET = (
    "import json, sys;"
    "from instrumentalize import convert_score;"
    "converted, check = convert_score(sys.stdin.read());"
    "print(json.dumps({'score': converted, 'check': check}))"
)


def instrumentalize_score(abc_text, timeout=60):
    """Move Vocal notes to the Ins voice via the instrumental skill (subprocess).

    The instrumental scripts share flat module names (abc_tools et al.) with
    ABC_TOOLS, so they must not be imported into this process. Returns
    (converted_abc, check_report); raises on transfer failure.
    """
    proc = subprocess.run([sys.executable, "-B", "-c", TRANSFER_SNIPPET],
                          cwd=str(INSTRUMENTAL_SCRIPTS), input=abc_text,
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip().splitlines()[-1] if proc.stderr.strip()
                           else f"exit code {proc.returncode}")
    payload = json.loads(proc.stdout)
    return payload["score"], payload["check"]


def audio_duration(path):
    try:
        import soundfile as sf
        info = sf.info(str(path))
        return info.frames / info.samplerate
    except Exception:
        return None


def queue_song(title, style, lyrics, cot, seed, instrumental, parent_id, abc=None, cfg_scale=None, lora=None,
               backend="torch", plan_only=False, sampling=None, vocal_gender=None):
    from yue2.style_localization import (contains_cjk, default_chain,
                                         ensure_instrumental_tag, llm_provider,
                                         localize_style)
    style_language = settings.get("style_language")
    style, style_original, translated = localize_style(
        style, style_language, provider_chain=default_chain(llm_provider(settings.data)))
    if vocal_gender in {"male", "female"} and not instrumental:
        style += f", {vocal_gender} vocals"
    if instrumental:
        style = ensure_instrumental_tag(style)
    transfer_check = None
    instrumental_warning = None
    if instrumental and abc is not None:
        pre_transfer = abc
        try:
            abc, transfer_check = instrumentalize_score(abc)
            if not transfer_check["vocal_notes_before"]:
                transfer_check = None
        except Exception as exc:  # noqa: BLE001 - transfer failure must not block generation
            transfer_check = None
            instrumental_warning = f"{type(exc).__name__}: {exc}"
    style_warning = None
    if not translated and contains_cjk(style):
        style_warning = ("Style was not translated (no translation provider available); "
                         "generation continues with the original text")
    song_id = new_item_id(title)
    song = {
        "id": song_id, "kind": "song", "title": title,
        "style": style, "lyrics": lyrics, "cot": cot, "seed": seed, "cfg_scale": cfg_scale,
        "instrumental": instrumental, "lora": lora, "backend": backend,
        "plan_only": plan_only, "sampling": sampling or {},
        "status": "queued", "stage": None, "progress": {},
        "error": None, "created_at": time.time(), "audio_seconds": None,
        "has_score": abc is not None or cot != "off", "truncated": None, "parent_id": parent_id,
    }
    if style_original is not None:
        song["style_original"] = style_original
    if style_warning is not None:
        song["style_warning"] = style_warning
    if instrumental_warning is not None:
        song["instrumental_warning"] = instrumental_warning
    if transfer_check is not None:
        song["transfer"] = {"vocal_notes_before": transfer_check["vocal_notes_before"],
                            "output_ins_notes": transfer_check["output_ins_notes"],
                            "unaltered_ins_notes": transfer_check["unaltered_ins_notes"]}
    library.put(song)
    if transfer_check is not None:
        folder = OUTPUTS / song_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "score.model.abc").write_text(pre_transfer, encoding="utf-8")
        (folder / "transfer.json").write_text(json.dumps(transfer_check, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    kwargs = {"style": style, "lyrics": lyrics, "cot": cot, "seed": seed, "id": song_id,
              "style_language": style_language, "instrumental": instrumental}
    if style_original is not None:
        kwargs["style_original"] = style_original
    if abc is not None:
        kwargs["abc"] = abc
    if cfg_scale is not None:
        kwargs["cfg_scale"] = cfg_scale
    if lora is not None:
        kwargs["lora"] = lora
    if sampling:
        kwargs["sampling"] = sampling
    if plan_only:
        kwargs["plan_only"] = True
    runner.submit("generate_mlx" if backend == "mlx" else "generate", song_id, kwargs)
    return song


def queue_from_request(body):
    """Validate one CreateSong payload and queue it; shared by single and batch create."""
    if body.cot not in {"off", "melody", "full"}:
        raise HTTPException(422, "cot must be off, melody or full")
    if body.cfg_scale is not None and not 0 <= body.cfg_scale <= 20:
        raise HTTPException(422, "cfg_scale must be in [0, 20]")
    backend = body.backend or default_backend_effective()
    if backend not in {"torch", "mlx"}:
        raise HTTPException(422, "backend must be torch or mlx")
    if backend == "mlx":
        if not mlx_available():
            raise HTTPException(422, "The MLX backend is not installed (run tools/download_mlx.sh)")
        if body.lora is not None:
            raise HTTPException(422, "LoRA adapters are not supported by the MLX backend")
    if body.lora is not None and not lora_path(body.lora).exists():
        raise HTTPException(422, f"LoRA adapter '{body.lora}' is not installed")
    if body.temperature is not None and not 0 <= body.temperature <= 3:
        raise HTTPException(422, "temperature must be in [0, 3]")
    if body.top_p is not None and not 0 < body.top_p <= 1:
        raise HTTPException(422, "top_p must be in (0, 1]")
    if body.top_k is not None and not 1 <= body.top_k <= 1000:
        raise HTTPException(422, "top_k must be in [1, 1000]")
    if body.max_seconds is not None and not 5 <= body.max_seconds <= 360:
        raise HTTPException(422, "max_seconds must be in [5, 360]")
    if body.ode_steps is not None and not 2 <= body.ode_steps <= 64:
        raise HTTPException(422, "ode_steps must be in [2, 64]")
    if body.vocal_gender is not None and body.vocal_gender not in {"male", "female"}:
        raise HTTPException(422, "vocal_gender must be male or female")
    cot = body.cot
    abc = (body.abc or "").strip() or None
    if abc is not None:
        try:
            abc_report(abc)
        except Exception as exc:
            raise HTTPException(422, f"The score does not parse: {exc}")
        if cot == "off":
            cot = "full"
    if body.plan_only and abc is None and cot == "off":
        raise HTTPException(422, "plan_only needs cot full or melody")
    lyrics = "[Instrumental]" if body.instrumental else body.lyrics
    title = (body.title or "").strip() or "Untitled"
    seed = body.seed if body.seed is not None else random.randint(0, 2**31 - 1)
    sampling = {k: v for k, v in (("temperature", body.temperature), ("top_p", body.top_p),
                                  ("top_k", body.top_k), ("max_seconds", body.max_seconds),
                                  ("ode_steps", body.ode_steps)) if v is not None}
    return queue_song(title, body.style.strip(), lyrics, cot, seed, body.instrumental, None,
                      abc=abc, cfg_scale=body.cfg_scale, lora=body.lora, backend=backend,
                      plan_only=body.plan_only, sampling=sampling, vocal_gender=body.vocal_gender)


# ---------------------------------------------------------------------------
# API

app = FastAPI(title="YuE2 Studio", version="0.2.0")


class CreateSong(BaseModel):
    title: str | None = None
    style: str = Field(min_length=1)
    lyrics: str = ""
    cot: str = "full"
    seed: int | None = None
    cfg_scale: float | None = None
    instrumental: bool = False
    lora: str | None = None
    backend: str | None = None
    abc: str | None = None
    plan_only: bool = False
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_seconds: int | None = None
    ode_steps: int | None = None
    vocal_gender: str | None = None


class BatchCreate(BaseModel):
    requests: list[CreateSong]


class RedecodeRequest(BaseModel):
    decoder: str = "default"


class CompareRequest(BaseModel):
    ids: list[str]


class SettingsUpdate(BaseModel):
    decoder: str | None = None
    backend: str | None = None
    quantization: str | None = None
    offload_ar: bool | None = None
    budget: float | None = None
    style_language: str | None = None
    default_backend: str | None = None
    default_mode: str | None = None
    default_max_seconds: int | None = None
    default_cfg: float | None = None
    autoplay_on_complete: bool | None = None
    notify_on_complete: bool | None = None
    poll_interval: float | None = None
    mlx_variant: str | None = None
    start_view: str | None = None
    default_sort: str | None = None
    reduce_motion: bool | None = None
    download_source: str | None = None
    default_lora: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_timeout: float | None = None
    llm_enhance_output: str | None = None
    reset_defaults: bool | None = None


class EditSong(BaseModel):
    title: str | None = None
    style: str | None = None
    lyrics: str | None = None
    abc: str | None = None
    backend: str | None = None
    lora: str | None = None


class CoverSong(BaseModel):
    title: str | None = None
    style: str = Field(min_length=1)
    lyrics: str | None = None
    mode: str = "melody"  # melody = strip chords, free accompaniment; full = keep harmony
    instrumental: bool = False
    backend: str | None = None
    lora: str | None = None


class ScoreUpdate(BaseModel):
    abc: str = Field(min_length=1)


@app.get("/api/state")
def state():
    llm_items, llm_active_id = providers_snapshot()
    return {"model": runner.model_status(), "device": runner.device_name(),
            "model_error": runner.pipe_error, "queue": runner.jobs.qsize(),
            "current": runner.current_id, "transcribe_available": transcribe_available(),
            "core_installed": core_installed(),
            "mlx_available": mlx_available(), "vllm_available": vllm_available(),
            "decoder": settings.get("decoder"),
            "decoder_legacy_available": (VAE_LEGACY_DIR / "model.safetensors").exists(),
            "decoder_merge_available": (VAE_MERGE_DIR / "model.safetensors").exists(),
            "backend": settings.get("backend"), "quantization": settings.get("quantization"),
            "offload_ar": settings.get("offload_ar"), "budget": settings.get("budget"),
            "style_language": settings.get("style_language"),
            "default_backend": default_backend_effective(),
            "default_mode": settings.get("default_mode"),
            "default_max_seconds": settings.get("default_max_seconds"),
            "default_cfg": settings.get("default_cfg"),
            "autoplay_on_complete": settings.get("autoplay_on_complete"),
            "notify_on_complete": settings.get("notify_on_complete"),
            "poll_interval": settings.get("poll_interval"),
            "mlx_variant": mlx_variant_effective(), "mlx_variants": mlx_variants(),
            "start_view": settings.get("start_view"), "default_sort": settings.get("default_sort"),
            "reduce_motion": settings.get("reduce_motion"),
            "download_source": settings.get("download_source"),
            "download_active": downloads.snapshot(),
            "default_lora": settings.get("default_lora"),
            "llm_providers": llm_items,
            "llm_active_provider": llm_active_id,
            "llm_active": _llm_active_summary(),
            "llm_timeout": settings.get("llm_timeout"),
            "llm_enhance_output": settings.get("llm_enhance_output")}


@app.get("/api/settings")
def get_settings():
    llm_items, llm_active_id = providers_snapshot()
    return {"decoder": settings.get("decoder"),
            "decoder_legacy_available": (VAE_LEGACY_DIR / "model.safetensors").exists(),
            "llm_providers": llm_items,
            "llm_active_provider": llm_active_id,
            "llm_active": _llm_active_summary(),
            "llm_timeout": settings.get("llm_timeout"),
            "llm_enhance_output": settings.get("llm_enhance_output")}


@app.post("/api/settings")
def update_settings(body: SettingsUpdate):
    load_time_keys = {"backend", "quantization", "offload_ar", "budget"}
    changed = {}
    if body.decoder is not None:
        if body.decoder not in {"default", "legacy", "merge"}:
            raise HTTPException(422, "decoder must be default, legacy or merge")
        if body.decoder == "legacy" and not (VAE_LEGACY_DIR / "model.safetensors").exists():
            raise HTTPException(422, "The legacy decoder is not installed (run tools/download_extras.sh)")
        if body.decoder == "merge" and not (VAE_MERGE_DIR / "model.safetensors").exists():
            raise HTTPException(422, "The merge decoder is not installed (run tools/download_extras.sh)")
        changed["decoder"] = body.decoder
    if body.backend is not None:
        if body.backend not in {"torch", "vllm"}:
            raise HTTPException(422, "backend must be torch or vllm")
        if body.backend == "vllm" and not vllm_available():
            raise HTTPException(422, "vLLM is not installed in this environment (pip install vllm)")
        changed["backend"] = body.backend
    if body.quantization is not None:
        if body.quantization not in {"none", "fp8"}:
            raise HTTPException(422, "quantization must be none or fp8")
        if body.quantization == "fp8" and runner.device_name() != "cuda":
            raise HTTPException(422, "FP8 quantization needs a CUDA device")
        changed["quantization"] = body.quantization
    if body.offload_ar is not None:
        changed["offload_ar"] = bool(body.offload_ar)
    if body.budget is not None:
        if not 4 <= body.budget <= 1024:
            raise HTTPException(422, "budget must be in [4, 1024] GiB")
        changed["budget"] = float(body.budget)
    if body.style_language is not None:
        if body.style_language not in {"auto", "en", "off"}:
            raise HTTPException(422, "style_language must be auto, en or off")
        changed["style_language"] = body.style_language
    if body.default_backend is not None:
        if body.default_backend not in {"torch", "mlx"}:
            raise HTTPException(422, "default_backend must be torch or mlx")
        if body.default_backend == "mlx" and not mlx_available():
            raise HTTPException(422, "The MLX backend is not installed (run tools/download_mlx.sh)")
        changed["default_backend"] = body.default_backend
    if body.default_mode is not None:
        if body.default_mode not in {"simple", "advanced"}:
            raise HTTPException(422, "default_mode must be simple or advanced")
        changed["default_mode"] = body.default_mode
    if "default_max_seconds" in body.model_fields_set:
        # explicit null clears the preference back to "auto"
        if body.default_max_seconds is not None and not 5 <= body.default_max_seconds <= 360:
            raise HTTPException(422, "default_max_seconds must be in [5, 360]")
        changed["default_max_seconds"] = (int(body.default_max_seconds)
                                          if body.default_max_seconds is not None else None)
    if "default_cfg" in body.model_fields_set:
        if body.default_cfg is not None and not 0 <= body.default_cfg <= 20:
            raise HTTPException(422, "default_cfg must be in [0, 20]")
        changed["default_cfg"] = float(body.default_cfg) if body.default_cfg is not None else None
    if body.autoplay_on_complete is not None:
        changed["autoplay_on_complete"] = bool(body.autoplay_on_complete)
    if body.notify_on_complete is not None:
        changed["notify_on_complete"] = bool(body.notify_on_complete)
    if body.poll_interval is not None:
        if body.poll_interval not in {1.5, 3.0, 5.0, 10.0}:
            raise HTTPException(422, "poll_interval must be 1.5, 3, 5 or 10")
        changed["poll_interval"] = float(body.poll_interval)
    if body.mlx_variant is not None:
        if body.mlx_variant not in mlx_variants():
            raise HTTPException(422, f"mlx_variant must be one of the installed variants: {', '.join(mlx_variants()) or 'none'}")
        changed["mlx_variant"] = body.mlx_variant
    if body.start_view is not None:
        if body.start_view not in {"create", "library"}:
            raise HTTPException(422, "start_view must be create or library")
        changed["start_view"] = body.start_view
    if body.default_sort is not None:
        if body.default_sort not in {"new", "old", "title"}:
            raise HTTPException(422, "default_sort must be new, old or title")
        changed["default_sort"] = body.default_sort
    if body.reduce_motion is not None:
        changed["reduce_motion"] = bool(body.reduce_motion)
    if body.download_source is not None:
        if body.download_source not in DOWNLOAD_ENDPOINTS:
            raise HTTPException(422, "download_source must be mirror or huggingface")
        changed["download_source"] = body.download_source
    if "default_lora" in body.model_fields_set:
        if body.default_lora is not None and not lora_path(body.default_lora).exists():
            raise HTTPException(422, f"LoRA adapter '{body.default_lora}' is not installed")
        changed["default_lora"] = body.default_lora
    if body.llm_base_url is not None:
        value = body.llm_base_url.strip()
        if value and not re.match(r"^https?://", value):
            raise HTTPException(422, "llm_base_url must be an http(s) URL")
        changed["llm_base_url"] = value
    if body.llm_model is not None:
        changed["llm_model"] = body.llm_model.strip()
    if "llm_api_key" in body.model_fields_set:
        changed["llm_api_key"] = (body.llm_api_key or "").strip()
    if body.llm_timeout is not None:
        if not 1 <= body.llm_timeout <= 60:
            raise HTTPException(422, "llm_timeout must be in [1, 60] seconds")
        changed["llm_timeout"] = float(body.llm_timeout)
    if body.llm_enhance_output is not None:
        if body.llm_enhance_output not in {"zh", "en"}:
            raise HTTPException(422, "llm_enhance_output must be zh or en")
        changed["llm_enhance_output"] = body.llm_enhance_output
    if body.reset_defaults:
        changed = dict(DEFAULT_SETTINGS)
    reload_needed = bool(set(changed) & load_time_keys)
    if reload_needed and runner.current_id is not None:
        raise HTTPException(409, "A job is running; change this after it finishes")
    settings.update(**changed)
    if reload_needed:
        runner.reload_pipe()
    return state()


# ---------------------------------------------------------------------------
# LLM providers: presets, CRUD, model discovery, chat playground

LLM_PRESETS = [
    {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com", "needs_key": True},
    {"id": "qwen", "name": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "needs_key": True},
    {"id": "glm", "name": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4", "needs_key": True},
    {"id": "kimi", "name": "Kimi", "base_url": "https://api.moonshot.cn/v1", "needs_key": True},
    {"id": "minimax", "name": "MiniMax", "base_url": "https://api.minimaxi.com/v1", "needs_key": True},
    {"id": "openai", "name": "OpenAI", "base_url": "https://api.openai.com/v1", "needs_key": True},
    {"id": "ollama", "name": "Ollama", "base_url": "http://localhost:11434/v1", "needs_key": False},
    {"id": "custom", "name": "自定义", "base_url": "", "needs_key": False},
]
LLM_PRESET_IDS = {p["id"] for p in LLM_PRESETS}

MODELS_FETCH_TIMEOUT = 10.0
MODELS_MAX_RESPONSE = 1024 * 1024
MODELS_MAX_ITEMS = 500

CHATS_FILE = DATA / "llm_chats.json"
CHAT_CONTEXT_MESSAGES = 12
CHAT_CONTEXT_CHARS = 8000
CHAT_MAX_TEXT = 4000
CHAT_MAX_TOKENS = 2048
CHAT_TEMPERATURE = 0.7
CHAT_TOTAL_SECONDS = 120.0
CHAT_MAX_CONVERSATIONS = 100
CHAT_MAX_MESSAGES = 500


def mask_key(key):
    key = (key or "").strip()
    if not key:
        return ""
    return "••••" + key[-4:] if len(key) >= 8 else "••••"


def validate_base_url(url):
    """None when acceptable; otherwise a readable Chinese error (http only for loopback)."""
    if not url:
        return "接口地址不能为空"
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return "接口地址不是合法 URL"
    if parts.scheme not in ("http", "https"):
        return "仅支持 http/https 协议"
    if not parts.hostname:
        return "URL 缺少主机名"
    if parts.username or parts.password:
        return "URL 不允许内嵌用户名/密码"
    if parts.query or parts.fragment:
        return "URL 不允许带 query 或 fragment"
    if parts.scheme == "http":
        host = parts.hostname.lower()
        if host == "localhost":
            return None
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return "http 仅允许本机地址（localhost/127.x），远程服务请用 https"
        if not ip.is_loopback:
            return "http 仅允许本机地址（localhost/127.x），远程服务请用 https"
    return None


def _new_provider_id(providers):
    used = {p.get("id") for p in providers}
    while True:
        pid = "p" + uuid.uuid4().hex[:7]
        if pid not in used:
            return pid


def _legacy_provider_item():
    base_url = (settings.get("llm_base_url") or "").strip()
    model = (settings.get("llm_model") or "").strip()
    if not base_url or not model:
        return None
    return {"id": "legacy", "name": model, "preset": "custom", "base_url": base_url,
            "api_key": settings.get("llm_api_key") or "", "default_model": model,
            "enabled": True}


def providers_snapshot():
    """(masked items, active id) for API responses, synthesizing the legacy entry."""
    items = [dict(p) for p in (settings.get("llm_providers") or [])]
    legacy = False
    if not items:
        legacy_item = _legacy_provider_item()
        if legacy_item:
            items = [legacy_item]
            legacy = True
    active = "legacy" if legacy else settings.get("llm_active_provider")
    out = [{"id": p.get("id"), "name": p.get("name") or "", "preset": p.get("preset") or "custom",
            "base_url": p.get("base_url") or "", "default_model": p.get("default_model") or "",
            "enabled": bool(p.get("enabled", True)),
            "api_key_masked": mask_key(p.get("api_key"))} for p in items]
    return out, active


def _providers_for_mutation():
    """(items, active id, extra settings, legacy id) materializing the legacy config."""
    raw = [dict(p) for p in (settings.get("llm_providers") or [])]
    active = settings.get("llm_active_provider")
    extra = {}
    legacy_id = None
    if not raw:
        legacy_item = _legacy_provider_item()
        if legacy_item:
            legacy_item["id"] = _new_provider_id(raw)
            raw = [legacy_item]
            legacy_id = legacy_item["id"]
            if active in (None, "", "legacy"):
                active = legacy_item["id"]
            extra = {"llm_base_url": "", "llm_model": "", "llm_api_key": ""}
    return raw, active, extra, legacy_id


def _llm_active_summary():
    """Lightweight active-endpoint summary for /api/state (no key material)."""
    from yue2.style_localization import active_provider
    active = active_provider(settings.data)
    if active is None:
        return None
    return {"id": active["id"], "name": active["name"] or active["default_model"],
            "model": active["default_model"], "preset": active["preset"]}


def _provider_by_id(provider_id):
    """Stored provider entry (or the synthesized legacy one), with raw key."""
    if not provider_id:
        return None
    items = [dict(p) for p in (settings.get("llm_providers") or [])]
    if not items:
        legacy_item = _legacy_provider_item()
        if legacy_item and provider_id == "legacy":
            return legacy_item
        return None
    return next((p for p in items if p.get("id") == provider_id), None)


class LlmProviderPayload(BaseModel):
    name: str | None = None
    preset: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    enabled: bool | None = None


class LlmActivePayload(BaseModel):
    provider_id: str | None = None


class LlmTestRequest(BaseModel):
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    timeout: float | None = None
    provider_id: str | None = None


class EnhanceRequest(BaseModel):
    style: str = Field(min_length=1, max_length=500)


def _llm_error(exc):
    text = str(exc).strip() or exc.__class__.__name__
    return text[:200]


@app.get("/api/llm/presets")
def llm_presets():
    return {"items": LLM_PRESETS}


@app.get("/api/llm/providers")
def llm_providers_list():
    items, active = providers_snapshot()
    return {"items": items, "active": active}


def _providers_response(changed):
    settings.update(**changed)
    items, active = providers_snapshot()
    return {"items": items, "active": active}


@app.post("/api/llm/providers")
def llm_provider_create(body: LlmProviderPayload):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(422, "供应商名称不能为空")
    preset = body.preset or "custom"
    if preset not in LLM_PRESET_IDS:
        raise HTTPException(422, "未知的预设平台")
    base_url = (body.base_url or "").strip().rstrip("/")
    if base_url:
        err = validate_base_url(base_url)
        if err:
            raise HTTPException(422, err)
    raw, active, extra, _legacy_id = _providers_for_mutation()
    raw.append({"id": _new_provider_id(raw), "name": name, "preset": preset,
                "base_url": base_url, "api_key": (body.api_key or "").strip(),
                "default_model": (body.default_model or "").strip(),
                "enabled": True if body.enabled is None else bool(body.enabled)})
    return _providers_response({"llm_providers": raw, "llm_active_provider": active, **extra})


@app.put("/api/llm/providers/{provider_id}")
def llm_provider_update(provider_id: str, body: LlmProviderPayload):
    raw, active, extra, legacy_id = _providers_for_mutation()
    if provider_id == "legacy" and legacy_id:
        provider_id = legacy_id
    entry = next((p for p in raw if p.get("id") == provider_id), None)
    if entry is None:
        raise HTTPException(404, "provider not found")
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "供应商名称不能为空")
        entry["name"] = name
    if body.preset is not None:
        if body.preset not in LLM_PRESET_IDS:
            raise HTTPException(422, "未知的预设平台")
        entry["preset"] = body.preset
    if body.base_url is not None:
        base_url = body.base_url.strip().rstrip("/")
        if base_url:
            err = validate_base_url(base_url)
            if err:
                raise HTTPException(422, err)
        entry["base_url"] = base_url
    if "api_key" in body.model_fields_set:
        entry["api_key"] = (body.api_key or "").strip()
    if body.default_model is not None:
        entry["default_model"] = body.default_model.strip()
    if body.enabled is not None:
        entry["enabled"] = bool(body.enabled)
    return _providers_response({"llm_providers": raw, "llm_active_provider": active, **extra})


@app.delete("/api/llm/providers/{provider_id}")
def llm_provider_delete(provider_id: str):
    raw, active, extra, legacy_id = _providers_for_mutation()
    if provider_id == "legacy" and legacy_id:
        provider_id = legacy_id
    before = len(raw)
    raw = [p for p in raw if p.get("id") != provider_id]
    if len(raw) == before:
        raise HTTPException(404, "provider not found")
    if active == provider_id:
        active = None
    return _providers_response({"llm_providers": raw, "llm_active_provider": active, **extra})


@app.post("/api/llm/active")
def llm_set_active(body: LlmActivePayload):
    raw, _active, extra, legacy_id = _providers_for_mutation()
    pid = (body.provider_id or "").strip() or None
    if pid == "legacy" and legacy_id:
        pid = legacy_id
    if pid is not None and not any(p.get("id") == pid for p in raw):
        raise HTTPException(404, "provider not found")
    return _providers_response({"llm_providers": raw, "llm_active_provider": pid, **extra})


# ---------------------------------------------------------------- model list

class LlmModelsRequest(BaseModel):
    preset: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    provider_id: str | None = None


def _llm_fail(code, message):
    return {"ok": False, "items": [], "message": message, "error_code": code}


def _read_capped(resp):
    body = resp.read(MODELS_MAX_RESPONSE + 1)
    if len(body) > MODELS_MAX_RESPONSE:
        raise ValueError("too_large")
    return body


def _fetch_models_once(base_url, api_key):
    url = base_url + "/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=MODELS_FETCH_TIMEOUT) as resp:
            body = _read_capped(resp)
    except ValueError:
        return _llm_fail("too_large", "响应超过 1MB 上限")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return _llm_fail("auth_failed", f"鉴权失败（HTTP {exc.code}），请检查 API Key")
        if exc.code == 429:
            return _llm_fail("rate_limited", "触发限流（HTTP 429），请稍后重试")
        detail = ""
        try:
            detail = exc.read(300).decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001
            pass
        return _llm_fail("http_error", f"HTTP {exc.code}：{detail}")
    except (TimeoutError, urllib.error.URLError) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError):
            return _llm_fail("timeout", f"请求超时（{MODELS_FETCH_TIMEOUT:g}s）")
        return _llm_fail("connect_failed", f"连接失败：{reason}")
    except OSError as exc:
        return _llm_fail("connect_failed", f"连接失败：{exc}")
    try:
        data = json.loads(body.decode("utf-8", "replace"))
        items = [str(m["id"]) for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
    except (ValueError, TypeError):
        return _llm_fail("bad_response", "响应不是合法的 OpenAI models 格式")
    items = sorted(set(items))[:MODELS_MAX_ITEMS]
    return {"ok": True, "items": items, "message": f"拉取到 {len(items)} 个模型"}


def _fetch_ollama_tags(base_url):
    try:
        with urllib.request.urlopen(base_url + "/api/tags", timeout=MODELS_FETCH_TIMEOUT) as resp:
            body = _read_capped(resp)
    except (TimeoutError, urllib.error.URLError, OSError, ValueError):
        return None
    try:
        data = json.loads(body.decode("utf-8", "replace"))
        items = [str(m["name"]) for m in data.get("models", []) if isinstance(m, dict) and m.get("name")]
    except (ValueError, TypeError):
        return None
    items = sorted(set(items))[:MODELS_MAX_ITEMS]
    return {"ok": True, "items": items, "message": f"拉取到 {len(items)} 个模型（ollama 原生协议）"}


@app.post("/api/llm/models")
def llm_fetch_models(body: LlmModelsRequest):
    base_url = (body.base_url or "").strip().rstrip("/")
    err = validate_base_url(base_url)
    if err:
        return _llm_fail("invalid_url", err)
    preset = body.preset or "custom"
    api_key = (body.api_key or "").strip()
    if not api_key and body.provider_id:
        entry = _provider_by_id(body.provider_id)
        if entry is not None:
            api_key = (entry.get("api_key") or "").strip()
    if not api_key:
        preset_info = next((p for p in LLM_PRESETS if p["id"] == preset), None)
        if preset_info and preset_info["needs_key"]:
            return _llm_fail("auth_failed", f"「{preset_info['name']}」需要 API Key，请先填写")
    result = _fetch_models_once(base_url, api_key)
    if result["ok"] or preset != "ollama":
        return result
    native = base_url[:-3] if base_url.endswith("/v1") else base_url
    fallback = _fetch_ollama_tags(native)
    return fallback if fallback is not None else result


# ---------------------------------------------------------------- connectivity

@app.post("/api/llm/test")
def llm_test(body: LlmTestRequest):
    from yue2.style_localization import LlmProvider, llm_provider
    entry = _provider_by_id(body.provider_id) if body.provider_id else None
    saved = llm_provider(settings.data)
    base_url = ((body.base_url or "").strip() or ((entry or {}).get("base_url") or "")
                or (saved.base_url if saved else ""))
    model = ((body.model or "").strip() or ((entry or {}).get("default_model") or "")
             or (saved.model if saved else ""))
    if not base_url or not model:
        raise HTTPException(422, "base_url and model are required")
    if "api_key" in body.model_fields_set and body.api_key is not None:
        api_key = body.api_key.strip() or None
    elif entry is not None:
        api_key = (entry.get("api_key") or "").strip() or None
    else:
        api_key = saved.api_key if saved else None
    timeout = body.timeout if body.timeout is not None else (saved.timeout if saved else 10.0)
    provider = LlmProvider(base_url, model, api_key, timeout)
    started = time.monotonic()
    try:
        provider.chat("You are a connectivity probe. Reply with OK.", "ping")
    except Exception as exc:  # noqa: BLE001 - any failure is a test result
        return {"ok": False, "error": _llm_error(exc)}
    return {"ok": True, "latency_ms": int((time.monotonic() - started) * 1000)}


@app.post("/api/llm/enhance")
def llm_enhance(body: EnhanceRequest):
    from yue2.style_localization import (enhancement_prompt, llm_provider,
                                         sanitize_enhanced_style)
    provider = llm_provider(settings.data)
    if provider is None:
        raise HTTPException(409, "LLM endpoint is not configured")
    mode = settings.get("llm_enhance_output") or "zh"
    try:
        prompt = enhancement_prompt(mode)
    except (OSError, ValueError) as exc:
        raise HTTPException(500, f"style dictionary unavailable: {exc}")
    try:
        raw = provider.chat(prompt, body.style)
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller
        raise HTTPException(502, f"LLM request failed: {_llm_error(exc)}")
    cleaned = sanitize_enhanced_style(raw)
    if not cleaned:
        raise HTTPException(502, "LLM returned no usable tags")
    return {"style": cleaned}


# ---------------------------------------------------------------- chat store

class ChatStore:
    """Conversation log for the LLM playground (web/data/llm_chats.json)."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.conversations = []
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                items = saved.get("conversations") if isinstance(saved, dict) else None
                if isinstance(items, list):
                    self.conversations = [c for c in items
                                          if isinstance(c, dict) and c.get("id")]
            except (ValueError, OSError):
                pass

    def _flush_locked(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"conversations": self.conversations},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _meta(conv):
        return {"id": conv.get("id"), "title": conv.get("title") or "",
                "created_at": conv.get("created_at"), "updated_at": conv.get("updated_at"),
                "provider_id": conv.get("provider_id"), "model": conv.get("model")}

    def _find_locked(self, conversation_id):
        return next((c for c in self.conversations if c.get("id") == conversation_id), None)

    def _prune_locked(self):
        if len(self.conversations) > CHAT_MAX_CONVERSATIONS:
            self.conversations.sort(key=lambda c: c.get("updated_at") or 0, reverse=True)
            self.conversations = self.conversations[:CHAT_MAX_CONVERSATIONS]

    def list(self):
        with self.lock:
            ordered = sorted(self.conversations, key=lambda c: c.get("updated_at") or 0,
                             reverse=True)
            return [self._meta(c) for c in ordered]

    def create(self, title=None):
        with self.lock:
            now = time.time()
            conv = {"id": "c" + uuid.uuid4().hex[:7], "title": (title or "").strip(),
                    "created_at": now, "updated_at": now, "provider_id": None, "model": None,
                    "messages": []}
            self.conversations.insert(0, conv)
            self._prune_locked()
            self._flush_locked()
            return self._meta(conv)

    def get(self, conversation_id):
        with self.lock:
            conv = self._find_locked(conversation_id)
            if conv is None:
                return None
            return {"conversation": self._meta(conv),
                    "messages": [dict(m) for m in conv.get("messages") or []]}

    _UNSET = object()

    def update(self, conversation_id, title=_UNSET, provider_id=_UNSET, model=_UNSET):
        with self.lock:
            conv = self._find_locked(conversation_id)
            if conv is None:
                return None
            if title is not self._UNSET and title is not None:
                conv["title"] = title.strip()[:60]
            if provider_id is not self._UNSET:
                conv["provider_id"] = provider_id or None
            if model is not self._UNSET:
                conv["model"] = model or None
            conv["updated_at"] = time.time()
            self._flush_locked()
            return self._meta(conv)

    def delete(self, conversation_id):
        with self.lock:
            before = len(self.conversations)
            self.conversations = [c for c in self.conversations
                                  if c.get("id") != conversation_id]
            if len(self.conversations) == before:
                return False
            self._flush_locked()
            return True

    def append_message(self, conversation_id, role, content):
        with self.lock:
            conv = self._find_locked(conversation_id)
            if conv is None:
                return None
            messages = conv.setdefault("messages", [])
            message = {"role": role, "content": content, "ts": time.time()}
            messages.append(message)
            if len(messages) > CHAT_MAX_MESSAGES:
                del messages[:len(messages) - CHAT_MAX_MESSAGES]
            if role == "user" and not conv.get("title"):
                first_line = " ".join(content.split())[:24]
                if first_line:
                    conv["title"] = first_line
            conv["updated_at"] = message["ts"]
            self._flush_locked()
            return dict(message)

    def set_last_content(self, conversation_id, content):
        """Update the trailing assistant message (incremental streaming persist)."""
        with self.lock:
            conv = self._find_locked(conversation_id)
            if conv is None:
                return None
            messages = conv.get("messages") or []
            if not messages or messages[-1].get("role") != "assistant":
                return None
            messages[-1]["content"] = content
            conv["updated_at"] = time.time()
            self._flush_locked()
            return dict(messages[-1])


chats = ChatStore(CHATS_FILE)


class ChatCreate(BaseModel):
    title: str | None = None


class ChatUpdate(BaseModel):
    title: str | None = None
    provider_id: str | None = None
    model: str | None = None


class ChatTurn(BaseModel):
    conversation_id: str
    text: str
    provider_id: str | None = None
    model: str | None = None


@app.get("/api/llm/conversations")
def chat_conversations():
    return {"items": chats.list()}


@app.post("/api/llm/conversations")
def chat_conversation_create(body: ChatCreate | None = None):
    return {"conversation": chats.create(title=(body.title if body else None))}


@app.get("/api/llm/conversations/{conversation_id}")
def chat_conversation_get(conversation_id: str):
    detail = chats.get(conversation_id)
    if detail is None:
        raise HTTPException(404, "conversation not found")
    return detail


@app.put("/api/llm/conversations/{conversation_id}")
def chat_conversation_update(conversation_id: str, body: ChatUpdate):
    kwargs = {}
    if body.title is not None:
        kwargs["title"] = body.title
    if "provider_id" in body.model_fields_set:
        kwargs["provider_id"] = body.provider_id
    if "model" in body.model_fields_set:
        kwargs["model"] = body.model
    meta = chats.update(conversation_id, **kwargs) if kwargs else None
    if meta is None:
        existing = chats.get(conversation_id)
        if existing is None:
            raise HTTPException(404, "conversation not found")
        meta = existing["conversation"]
    return {"conversation": meta}


@app.delete("/api/llm/conversations/{conversation_id}")
def chat_conversation_delete(conversation_id: str):
    if not chats.delete(conversation_id):
        raise HTTPException(404, "conversation not found")
    return {"ok": True}


def _sse(payload):
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def _resolve_chat_provider(provider_id, model):
    """(base_url, api_key, model, provider_id) for a chat turn, else None."""
    from yue2.style_localization import active_provider, llm_provider
    entry = _provider_by_id(provider_id) if provider_id else None
    if entry is not None and entry.get("enabled", True):
        base_url = (entry.get("base_url") or "").strip()
        use_model = (model or "").strip() or (entry.get("default_model") or "").strip()
        if base_url and use_model:
            return base_url, (entry.get("api_key") or "").strip(), use_model, entry.get("id")
    active = active_provider(settings.data)
    if active is not None:
        use_model = (model or "").strip() or active["default_model"]
        return active["base_url"], (active.get("api_key") or "").strip(), use_model, active["id"]
    fallback = llm_provider(settings.data)
    if fallback is None:
        return None
    use_model = (model or "").strip() or fallback.model
    return fallback.base_url, (fallback.api_key or ""), use_model, None


@app.post("/api/llm/chat")
def llm_chat(body: ChatTurn):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(422, "text is required")
    if len(text) > CHAT_MAX_TEXT:
        raise HTTPException(422, f"text is too long (max {CHAT_MAX_TEXT} chars)")
    detail = chats.get(body.conversation_id)
    if detail is None:
        raise HTTPException(404, "conversation not found")
    conversation = detail["conversation"]
    provider_id = (body.provider_id or conversation.get("provider_id") or "").strip() or None
    resolved = _resolve_chat_provider(provider_id, body.model or conversation.get("model"))
    if resolved is None:
        raise HTTPException(409, "LLM endpoint is not configured")
    base_url, api_key, model, used_id = resolved
    history = []
    total = 0
    for message in reversed(detail["messages"]):
        if len(history) >= CHAT_CONTEXT_MESSAGES:
            break
        content = message.get("content") or ""
        if history and total + len(content) > CHAT_CONTEXT_CHARS:
            break
        if message.get("role") in {"user", "assistant"}:
            history.append({"role": message["role"], "content": content})
            total += len(content)
    history.reverse()
    chats.append_message(body.conversation_id, "user", text)
    chats.update(body.conversation_id, provider_id=used_id, model=model)
    payload = {"model": model, "messages": history + [{"role": "user", "content": text}],
               "stream": True, "max_tokens": CHAT_MAX_TOKENS, "temperature": CHAT_TEMPERATURE}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(base_url.rstrip("/") + "/chat/completions",
                                     data=json.dumps(payload).encode("utf-8"), headers=headers)
    timeout = float(settings.get("llm_timeout") or 10.0)
    try:
        upstream = urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise HTTPException(502, f"LLM request failed: HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001 - surfaced before the stream starts
        raise HTTPException(502, f"LLM request failed: {_llm_error(exc)}")
    conversation_id = body.conversation_id

    def generate():
        collected = []
        saved_once = False
        last_save = 0.0
        aborted = False
        deadline = time.monotonic() + CHAT_TOTAL_SECONDS

        def persist_partial():
            nonlocal saved_once, last_save
            content = "".join(collected)
            if not content:
                return
            try:
                if not saved_once:
                    chats.append_message(conversation_id, "assistant", content)
                    saved_once = True
                else:
                    chats.set_last_content(conversation_id, content)
                last_save = time.monotonic()
            except Exception:  # noqa: BLE001 - persistence must not break the stream
                pass

        try:
            for raw_line in upstream:
                if time.monotonic() > deadline:
                    aborted = True
                    persist_partial()
                    yield _sse({"error": "总时长超过 120 秒限制，已中断"})
                    break
                line = raw_line.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                except ValueError:
                    continue
                choices = data.get("choices") or [{}]
                piece = ((choices[0].get("delta") or {}).get("content")) or ""
                if piece:
                    collected.append(piece)
                    if not saved_once or time.monotonic() - last_save >= 0.2:
                        persist_partial()
                    yield _sse({"delta": piece})
            persist_partial()
            if not aborted:
                yield "data: [DONE]\n\n"
        except Exception as exc:  # noqa: BLE001 - mid-stream failure surfaces as an event
            persist_partial()
            yield _sse({"error": _llm_error(exc)})
        finally:
            try:
                upstream.close()
            except Exception:  # noqa: BLE001
                pass
            persist_partial()

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class ModelDownload(BaseModel):
    component: str
    source: str | None = None


class ModelCancel(BaseModel):
    component: str


def cuda_kit_entry() -> dict | None:
    """Model-page row for the Windows CUDA acceleration kit (None off Windows)."""
    if cuda_kit is None or sys.platform != "win32":
        return None
    status = cuda_kit.status()
    job = status.get("job") or {}
    total = int(job.get("total_bytes") or 0) or cuda_kit.size_bytes()
    return {"id": "cuda-kit", "group": "cuda",
            "label": "CUDA 加速套件（NVIDIA GPU）",
            "bytes": total, "required": False,
            "installed": bool(status.get("installed")),
            "downloaded_bytes": int(job.get("downloaded_bytes") or 0),
            "downloading": job.get("status") == "running",
            "error": job.get("error"),
            "cuda": status}


def _models_payload():
    active = downloads.snapshot()
    components = []
    for comp in MODEL_COMPONENTS:
        if comp["platform"] and sys.platform != comp["platform"]:
            continue
        if comp.get("mode") == "cuda-kit":
            entry = cuda_kit_entry()
            if entry is not None:
                components.append(entry)
            continue
        installed = all((ROOT / "models" / rel).exists() for rel in comp["paths"])
        entry = {"id": comp["id"], "group": comp["group"], "label": comp["label"],
                 "bytes": comp["bytes"], "required": comp["required"],
                 "installed": installed, "downloaded_bytes": 0 if installed else _component_bytes(comp),
                 "downloading": False, "error": None}
        if active and active["component"] == comp["id"]:
            if active.get("running"):
                entry["downloading"] = True
            entry["error"] = active["error"]
        components.append(entry)
    return {"components": components, "download": active}


@app.get("/api/models")
def models_state():
    return _models_payload()


@app.post("/api/models/download")
def models_download(body: ModelDownload):
    comp = MODEL_COMPONENTS_BY_ID.get(body.component)
    if comp is None:
        raise HTTPException(422, f"Unknown component '{body.component}'")
    if comp["platform"] and sys.platform != comp["platform"]:
        raise HTTPException(422, "This component is not available on this platform")
    if comp.get("mode") == "cuda-kit":
        if cuda_kit is None or not cuda_kit.status().get("supported"):
            raise HTTPException(422, "CUDA 加速套件仅支持 Windows 平台")
        try:
            cuda_kit.start_download()
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI verbatim
            raise HTTPException(409, str(exc)) from exc
        return _models_payload()
    if all((ROOT / "models" / rel).exists() for rel in comp["paths"]):
        raise HTTPException(409, "This component is already installed")
    source = body.source or settings.get("download_source") or "mirror"
    if source not in DOWNLOAD_ENDPOINTS:
        raise HTTPException(422, "source must be mirror or huggingface")
    downloads.start(comp, source)
    return _models_payload()


@app.post("/api/models/cancel")
def models_cancel(body: ModelCancel):
    if body.component == "cuda-kit" and cuda_kit is not None:
        try:
            cuda_kit.cancel()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(409, str(exc)) from exc
        return _models_payload()
    downloads.cancel(body.component)
    return _models_payload()


@app.delete("/api/models/cuda-kit")
def cuda_kit_remove():
    if cuda_kit is None or sys.platform != "win32":
        raise HTTPException(422, "CUDA 加速套件仅支持 Windows 平台")
    try:
        cuda_kit.remove()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(409, str(exc)) from exc
    return _models_payload()


@app.get("/api/loras")
def get_loras():
    return list_loras()


@app.get("/api/songs")
def list_songs():
    return [public(s) for s in library.list()]


@app.post("/api/songs", status_code=201)
def create_song(body: CreateSong):
    return public(queue_from_request(body))


@app.post("/api/songs/batch", status_code=201)
def create_song_batch(body: BatchCreate):
    if not body.requests:
        raise HTTPException(422, "Batch needs at least one request")
    if len(body.requests) > 20:
        raise HTTPException(422, "A batch is limited to 20 requests")
    queued = [queue_from_request(item) for item in body.requests]
    return [public(s) for s in queued]


def resolve_model_choice(body, source):
    """Backend/LoRA for cover and edit: explicit request values win, otherwise inherit."""
    backend = body.backend if "backend" in body.model_fields_set else (source.get("backend") or default_backend_effective())
    lora = body.lora if "lora" in body.model_fields_set else source.get("lora")
    if backend not in {"torch", "mlx"}:
        raise HTTPException(422, "backend must be torch or mlx")
    if backend == "mlx":
        if not mlx_available():
            raise HTTPException(422, "The MLX backend is not installed (run tools/download_mlx.sh)")
        if lora is not None:
            raise HTTPException(422, "LoRA adapters are not supported by the MLX backend")
    if lora is not None and not lora_path(lora).exists():
        raise HTTPException(422, f"LoRA adapter '{lora}' is not installed")
    return backend, (lora or None)


@app.post("/api/songs/{song_id}/edit", status_code=201)
def edit_song(song_id: str, body: EditSong):
    source = get_item(song_id)
    if source["kind"] != "song":
        raise HTTPException(422, "Use Cover for uploaded audio")
    backend, lora = resolve_model_choice(body, source)
    style = (body.style or source["style"]).strip()
    lyrics = source["lyrics"] if body.lyrics is None else body.lyrics
    abc = body.abc if body.abc is not None else None
    cot = source["cot"]
    if abc is not None and cot == "off":
        raise HTTPException(422, "This song has no score (cot=off); edit style/lyrics instead")
    title = (body.title or "").strip() or f"{source['title']} (edit)"
    return public(queue_song(title, style, lyrics, cot, random.randint(0, 2**31 - 1),
                             source["instrumental"], song_id, abc=abc,
                             cfg_scale=source.get("cfg_scale"), lora=lora, backend=backend))


@app.post("/api/songs/{song_id}/cover", status_code=201)
def cover_song(song_id: str, body: CoverSong):
    source = get_item(song_id)
    backend, lora = resolve_model_choice(body, source)
    abc = current_score(source)
    if abc is None:
        raise HTTPException(422, "This item has no score to cover from")
    if body.mode not in {"melody", "full"}:
        raise HTTPException(422, "mode must be melody or full")
    if body.mode == "melody":
        abc = strip_abc_chords(abc)
    lyrics = "[Instrumental]" if body.instrumental else (body.lyrics if body.lyrics is not None else source.get("lyrics", ""))
    if not body.instrumental and not lyrics.strip():
        raise HTTPException(422, "A cover needs lyrics, or enable Instrumental")
    title = (body.title or "").strip() or f"{source['title']} (cover)"
    return public(queue_song(title, body.style.strip(), lyrics, body.mode,
                             random.randint(0, 2**31 - 1), body.instrumental, song_id, abc=abc,
                             lora=lora, backend=backend))


@app.get("/api/songs/{song_id}")
def song_detail(song_id: str):
    song = get_item(song_id)
    detail = public(song) | {"lyrics": song.get("lyrics", ""), "abc": None, "edited_abc": None}
    folder = item_folder(song)
    for rel in ("score.abc", "transcription/score.abc"):
        path = folder / rel
        if path.exists():
            detail["abc"] = path.read_text(encoding="utf-8")
            break
    edited = folder / "edited_score.abc"
    if edited.exists():
        detail["edited_abc"] = edited.read_text(encoding="utf-8")
    detail["has_latents"] = (folder / "latent.npy").exists()
    tech = {}
    for name in ("result.json", "request.json", "config.json", "transfer.json"):
        path = folder / name
        if path.exists():
            try:
                tech[name] = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                pass
    detail["tech"] = tech
    return detail


@app.get("/api/songs/{song_id}/score-check")
def score_check(song_id: str):
    song = get_item(song_id)
    abc = current_score(song)
    if abc is None:
        raise HTTPException(422, "This item has no score")
    try:
        return {"ok": True, "report": abc_report(abc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.get("/api/songs/{song_id}/audio")
def song_audio(song_id: str):
    song = get_item(song_id)
    folder = item_folder(song)
    if song["kind"] == "upload":
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in AUDIO_EXTS:
                return FileResponse(path, media_type=AUDIO_MIME.get(path.suffix.lower(), "audio/mpeg"))
        raise HTTPException(404, "Uploaded audio is missing")
    path = folder / "audio.flac"
    if not path.exists():
        raise HTTPException(404, "No audio for this song")
    return FileResponse(path, media_type="audio/flac", filename=f"{song_id}.flac")


@app.put("/api/songs/{song_id}/score")
def save_score(song_id: str, body: ScoreUpdate):
    song = get_item(song_id)
    if song["kind"] == "song" and song["cot"] == "off":
        raise HTTPException(422, "This song was generated without a score (cot=off)")
    folder = item_folder(song)
    folder.mkdir(parents=True, exist_ok=True)
    before = current_score(song)
    (folder / "edited_score.abc").write_text(body.abc, encoding="utf-8")
    response = {"ok": True, "report": None, "error": None, "diff": None}
    try:
        response["report"] = abc_report(body.abc)
    except Exception as exc:
        response["error"] = str(exc)
    if before is not None and response["error"] is None:
        try:
            response["diff"] = abc_compare(before, body.abc)
        except Exception:
            pass
    return response


class RebuildSong(BaseModel):
    title: str | None = None


@app.post("/api/songs/{song_id}/rebuild", status_code=201)
def rebuild_song(song_id: str, body: RebuildSong):
    source = get_item(song_id)
    if source.get("kind") != "upload":
        raise HTTPException(422, "Rebuild works on uploaded audio only")
    folder = UPLOADS / song_id
    if not folder.exists() or not any(p.suffix.lower() in AUDIO_EXTS for p in folder.iterdir()):
        raise HTTPException(422, "Uploaded audio is missing")
    if not REAUDIO_LORA.exists():
        raise HTTPException(422, "The realaudio pack is not installed (run tools/download_extras.sh)")
    if not transcribe_available():
        raise HTTPException(422, "The transcription environment is required for token extraction")
    title = (body.title or "").strip() or f"{source['title']} (rebuild)"
    song = {
        "id": new_item_id(title), "kind": "song", "title": title,
        "style": source.get("style") or "", "lyrics": source.get("lyrics") or "",
        "cot": "off", "seed": None, "cfg_scale": None, "instrumental": False,
        "lora": None, "backend": "torch", "plan_only": False, "sampling": {},
        "status": "queued", "stage": None, "progress": {}, "error": None,
        "created_at": time.time(), "audio_seconds": None, "has_score": False,
        "truncated": None, "parent_id": song_id,
    }
    library.put(song)
    runner.submit("rebuild", song["id"], {"source_id": song_id})
    return public(song)


@app.post("/api/songs/{song_id}/redecode")
def redecode_song(song_id: str, body: RedecodeRequest):
    song = get_item(song_id)
    if body.decoder not in {"default", "legacy", "merge"}:
        raise HTTPException(422, "decoder must be default, legacy or merge")
    if body.decoder in {"legacy", "merge"} and decoder_vae_path(body.decoder) is None:
        raise HTTPException(422, f"The {body.decoder} decoder is not installed (run tools/download_extras.sh)")
    if song["status"] != "complete":
        raise HTTPException(422, "Only finished songs can be re-decoded")
    if not (item_folder(song) / "latent.npy").exists():
        raise HTTPException(422, "This item has no saved latents to decode")
    library.update(song_id, status="queued", stage=None, error=None, progress={})
    runner.submit("redecode", song_id, {"decoder": body.decoder})
    return public(library.get(song_id))


def _dir_stats(path):
    total = count = latents = latent_count = 0
    if path.exists():
        for entry in path.rglob("*"):
            if not entry.is_file():
                continue
            try:
                size = entry.stat().st_size
            except OSError:
                continue
            total += size
            count += 1
            if entry.name == "latent.npy":
                latents += size
                latent_count += 1
    return {"bytes": total, "files": count, "latent_bytes": latents, "latent_files": latent_count}


@app.get("/api/storage")
def storage_stats():
    return {"outputs": _dir_stats(OUTPUTS), "uploads": _dir_stats(UPLOADS)}


@app.post("/api/storage/cleanup")
def storage_cleanup():
    if runner.current_id is not None:
        raise HTTPException(409, "A job is running; clean up after it finishes")
    freed = removed = 0
    for path in OUTPUTS.glob("*/latent.npy"):
        try:
            size = path.stat().st_size
            path.unlink()
        except OSError:
            continue
        freed += size
        removed += 1
    return {"freed_bytes": freed, "removed": removed}


@app.get("/api/examples")
def examples():
    scores = {}
    for name in ("melody.abc", "score.abc", "score-jazz.abc"):
        path = ROOT / "examples" / name
        if path.exists():
            scores[name] = path.read_text(encoding="utf-8")
    lyrics = []
    for path in sorted((ROOT / "examples").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        text = data.get("lyrics") if isinstance(data, dict) else None
        if isinstance(text, str) and text.strip():
            lyrics.append({"name": data.get("id") or path.stem,
                           "lyrics": text, "style": data.get("style") or ""})
    return {"scores": scores, "lyrics": lyrics}


# ---------------------------------------------------------------------------
# Environment doctor

DOCTOR_VERIFY = {"state": "idle", "results": None, "started": None}


def _verify_hashes():
    import hashlib
    results = []
    for label, folder in (("YuE2-3B", MODEL_DIR), ("YuE2-Vae", VAE_DIR), ("YuE2-Vae-legacy", VAE_LEGACY_DIR)):
        manifest = folder / "weights_manifest.json"
        target = folder / "model.safetensors"
        if not target.exists() or not manifest.exists():
            continue
        expected = json.loads(manifest.read_text(encoding="utf-8"))["files"]["model.safetensors"]["sha256"]
        start = time.perf_counter()
        digest = hashlib.sha256()
        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        results.append({"name": label, "ok": digest.hexdigest() == expected,
                        "seconds": round(time.perf_counter() - start, 1)})
    DOCTOR_VERIFY.update({"state": "done", "results": results})


@app.post("/api/doctor/verify")
def doctor_verify_start():
    if DOCTOR_VERIFY["state"] == "running":
        return {"state": "running"}
    DOCTOR_VERIFY.update({"state": "running", "results": None, "started": time.time()})
    threading.Thread(target=_verify_hashes, daemon=True, name="doctor-verify").start()
    return {"state": "running"}


@app.get("/api/doctor/verify")
def doctor_verify_state():
    return {"state": DOCTOR_VERIFY["state"], "results": DOCTOR_VERIFY["results"]}


@app.get("/api/doctor")
def doctor():
    checks = []
    for label, folder in (("YuE2-3B", MODEL_DIR), ("YuE2-Vae", VAE_DIR), ("YuE2-Vae-legacy", VAE_LEGACY_DIR)):
        target = folder / "model.safetensors"
        manifest = folder / "weights_manifest.json"
        expected = None
        if manifest.exists():
            try:
                expected = json.loads(manifest.read_text(encoding="utf-8"))["files"]["model.safetensors"]["bytes"]
            except (ValueError, KeyError):
                expected = None
        size = target.stat().st_size if target.exists() else None
        ok = size is not None and (expected is None or size == expected)
        checks.append({"group": "files", "name": label, "ok": ok,
                       "detail": f"{size} / {expected} bytes" if expected else ("present" if size else "missing")})
    checks.append({"group": "env", "name": "SheetSage2", "ok": transcribe_available(),
                   "detail": "ready" if transcribe_available() else "not installed"})
    checks.append({"group": "env", "name": "MLX (8-bit)", "ok": mlx_available(),
                   "detail": "ready" if mlx_available() else "not installed"})
    for l in list_loras():
        checks.append({"group": "lora", "name": l["label"], "ok": True,
                       "detail": " · ".join(x for x in (f"Rank {l.get('rank')}" if l.get("rank") else None,
                                                        (l.get("branch") or "").upper() or None) if x) or "LoRA"})
    return {"checks": checks, "device": runner.device_name(), "decoder": settings.get("decoder"),
            "verify": {"state": DOCTOR_VERIFY["state"], "results": DOCTOR_VERIFY["results"]}}


# ---------------------------------------------------------------------------
# Listening comparison page (skills/yue2-music/scripts/listen.py)

COMPARE_DIR = OUTPUTS / "comparisons"
COMPARE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/comparisons", StaticFiles(directory=str(COMPARE_DIR)), name="comparisons")


@app.post("/api/compare")
def make_compare(body: CompareRequest):
    ids = [i for i in body.ids if i]
    if len(ids) < 2 or len(ids) > 6:
        raise HTTPException(422, "Pick between 2 and 6 finished songs")
    folders = []
    for item_id in ids:
        song = get_item(item_id)
        if song["kind"] != "song" or song["status"] != "complete":
            raise HTTPException(422, "Only finished generated songs can be compared")
        folders.append(str(item_folder(song)))
    out = COMPARE_DIR / f"compare-{time.strftime('%Y%m%d-%H%M%S')}"
    script = ROOT / "skills" / "yue2-music" / "scripts" / "listen.py"
    proc = subprocess.run([sys.executable, str(script), *folders, "--output", str(out)],
                          capture_output=True, text=True, timeout=120,
                          encoding="utf-8", errors="replace")
    if proc.returncode not in (0, 1) or not (out / "index.html").exists():
        raise HTTPException(500, f"listen.py failed: {(proc.stderr or proc.stdout)[-300:]}")
    return {"url": f"/comparisons/{out.name}/index.html", "output": proc.stdout.strip()}


@app.post("/api/songs/{song_id}/cancel")
def cancel(song_id: str):
    song = get_item(song_id)
    if song["status"] == "queued":
        runner.cancel(song_id)
        library.update(song_id, status="cancelled", stage=None)
    elif song["status"] == "running":
        runner.cancel(song_id)
    return {"ok": True}


@app.delete("/api/songs/{song_id}")
def delete_song(song_id: str):
    song = get_item(song_id)
    runner.cancel(song_id)
    library.delete(song_id)
    folder = item_folder(song)
    if folder.exists():
        import shutil
        shutil.rmtree(folder)
    return {"ok": True}


@app.post("/api/uploads", status_code=201)
async def upload_audio(file: UploadFile = File(...), title: str = Form(default="")):
    if not transcribe_available():
        raise HTTPException(503, "SheetSage2 transcription is not installed on this machine")
    ext = Path(file.filename or "audio").suffix.lower()
    if ext not in AUDIO_EXTS:
        raise HTTPException(422, f"Unsupported audio format {ext or '(none)'}")
    data = await file.read()
    if len(data) > 200 * 1024 * 1024:
        raise HTTPException(413, "Audio file is too large (200 MB max)")
    name = title.strip() or Path(file.filename or "upload").stem
    item_id = new_item_id(name)
    folder = UPLOADS / item_id
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / f"source{ext}"
    source.write_bytes(data)
    song = {
        "id": item_id, "kind": "upload", "title": name, "style": "", "lyrics": "",
        "cot": None, "seed": None, "cfg_scale": None, "instrumental": False,
        "status": "queued", "stage": None, "progress": {}, "error": None,
        "created_at": time.time(), "audio_seconds": audio_duration(source),
        "has_score": False, "truncated": None, "parent_id": None,
    }
    library.put(song)
    runner.submit("transcribe", item_id)
    return public(song)


@app.get("/")
def index():
    return FileResponse(WEB / "static" / "index.html")


app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")


DEFAULT_PORT = 9086


def _valid_port(raw) -> int | None:
    try:
        port = int(raw)
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def _resolve_port(argv: list[str] | None = None) -> int:
    """Resolve the local port: ``--port`` > ``YUE2_PORT`` > :data:`DEFAULT_PORT`."""
    import argparse

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--port", dest="port")
    parsed, _ = parser.parse_known_args(argv)
    for source, raw in (("--port", parsed.port), ("YUE2_PORT", os.environ.get("YUE2_PORT"))):
        if raw in (None, ""):
            continue
        port = _valid_port(raw)
        if port is None:
            print(f"[warn] invalid {source}={raw!r}; using default port {DEFAULT_PORT}",
                  file=sys.stderr)
            return DEFAULT_PORT
        return port
    return DEFAULT_PORT


if __name__ == "__main__":
    import uvicorn

    _port = _resolve_port()
    print(f"YuE2 Studio  →  http://127.0.0.1:{_port}   (Ctrl+C to stop)")
    uvicorn.run(app, host="127.0.0.1", port=_port, log_level="info")
