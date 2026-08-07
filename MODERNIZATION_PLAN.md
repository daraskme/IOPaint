# IOPaint Modernization & Distribution Plan (2026-08)

Status: **REVISED r2** — incorporates Codex review r1 (session 019fdb5f-769a-7411-90f5-890258b69fce). All blocking issues and corrections addressed inline; changes vs r1 marked `[r2]`.
Author: Claude (Fable 5) — implementation by Codex (GPT 5.6 sol)
Base commit: 61a759f (upstream Sanster/IOPaint, 2025-04-29). Work branch: `modernize-2026`.

## 1. Goals

1. Upgrade all dependencies to Aug-2026 stable versions (backend + frontend).
2. Keep the current model lineup exactly as-is: LaMa (default), LDM, ZITS, MAT, FcF, Manga, MiGAN, cv2, SD1.5/SD2/SDXL inpaint, PowerPaint v1/v2, BrushNet, AnyText, Paint-by-Example, InstructPix2Pix, Kandinsky 2.2, ControlNet. **No Flux / Qwen-Image** (rejected by owner for speed/quality).
3. Targeted improvements where they are strict upgrades (§5).
4. Distributable fork: pyproject.toml packaging, CI from day one, PyPI trusted publishing, deterministic Windows/CUDA install.

### Non-goals
- No new heavy diffusion models; no UI redesign; no changes to inpaint quality/latency defaults.

### Reference environment
- Windows 11, RTX PRO 6000 Blackwell 96GB (**sm_120 → torch built with CUDA ≥ 12.8**), Python 3.11/3.12 installed. CI: Linux + Windows.

## 2. Dependency matrix (backend)

| Package | Current | Target | Notes |
|---|---|---|---|
| Python | >=3.7 | **>=3.10, <3.14** | `[r2]` upstream libs only force >=3.10; `<3.14` is OUR tested-support policy, encoded exactly as `requires-python = ">=3.10,<3.14"` and mirrored in CI (3.10/3.12/3.13) |
| torch | >=2.0.0 | **>=2.4, tested 2.13.x** | Blackwell needs cu128+ wheels. Not pinned exactly in metadata (users pick CPU/CUDA build) |
| torchvision | implicit | **explicit runtime dep** | `[r2]` imported directly by AnyText (`ldm/models/diffusion/ddpm.py:14`) and briarmbg2; every bootstrap path installs the torch/torchvision pair together |
| diffusers | ==0.27.2 | **==0.39.0** (exact pin) | vendored pipelines depend on internals; exact pin controls drift (§4.1) |
| transformers | >=4.39.1 | **>=5.14, <5.15** (tested minor pin) | v5 ships weekly breaking changes. **AnyText requires an explicit port, not verification** (§4.2) |
| huggingface_hub | ==0.25.2 | **>=1.3, <2** | httpx-based; hf_xet faster downloads free (§4.3) |
| accelerate | any | >=1.0 latest | |
| peft | ==0.7.1 | **>=0.17, <1** | verify PowerPaint v2 LoRA paths |
| safetensors | any | latest | |
| controlnet-aux | ==0.0.3 | **==0.0.10** | |
| fastapi | ==0.108.0 | **>=0.115, <1** (tested 0.141.x) | pydantic v2 already — low risk |
| uvicorn | any | `uvicorn[standard]` latest | |
| python-socketio | ==5.7.2 | **>=5.16, <6** | protocol v5 — socket.io-client 4.x stays compatible |
| pydantic | >=2.5.2 | >=2.9, <3 | |
| Pillow | ==9.5.0 | **>=11, <12** | `[r2]` AnyText uses BOTH removed APIs: `font.getsize` AND `font.getoffset` (`anytext/utils.py:69`) — port both (§4.5) |
| gradio | ==4.21.0 | **>=6, <7** as optional extra `[web-config]` | lazy import + clear error (§4.6) |
| onnxruntime | <=1.19.2 (installer.py pin) | **>=1.20** | `[r2]` `iopaint/installer.py` (`install-plugins-packages` CLI path) must be updated in the same change — it currently hard-pins `onnxruntime<=1.19.2` + unbounded rembg |
| rembg | plugin install | **>=2.0.78** | `[r2]` BiRefNet entries ALREADY exist in `schema.py:150` / `remove_bg.py` — this is a dependency/regression upgrade, not a feature add (§5.2) |
| piexif | ==1.1.3 | keep | stable |
| yacs / omegaconf / easydict | any | keep, latest | vendored ZITS/MAT/AnyText |
| typer / typer-config / rich / loguru | pinned-ish | latest compatible | |
| numpy | implicit | **>=2, <3** | `[r2]` active failures exist: `np.int0` in `anytext/cldm/recognizer.py:27`, `anytext/utils.py:84`, `anytext_pipeline.py:256,387` → `np.intp`. Full grep for all removed aliases across iopaint/ + scripts/ |

`pyproject.toml` is the single dependency authority; any `requirements*.txt` kept only as generated mirrors with a CI check that they match `[r2]`.

## 3. Dependency matrix (frontend, `web_app/`)

| Package | Current | Target | Notes |
|---|---|---|---|
| vite | ^5.0.0 | **^8.1** | `[r2]` 8.2 is prerelease-only; pin latest stable ^8.1.5 |
| @vitejs/plugin-react | ^4.2 | latest for Vite 8 | `[r2]` vite.config.ts uses plugin-react (NOT swc). Upgrade plugin-react; REMOVE unused `@vitejs/plugin-react-swc` from package.json |
| react / react-dom | ^18.2 | **^19.2** | types codemod (`types-react-codemod`) |
| typescript | ^5.2 | **^5.9** | |
| zustand | ^4.4 | **^5** | `[r2]` `states.ts` uses `createWithEqualityFn` from `zustand/traditional` → zustand 5 requires adding `use-sync-external-store` as a direct dependency. Also verify `zundo` v2 × zustand 5; if incompatible, hold zustand at ^4.5 (acceptable) |
| recoil | ^0.7.7 | **REMOVE** | unused (grep-verified), archived |
| @types/axios | present | **REMOVE** | axios ships own types |
| tailwindcss | ^3.3 | hold ^3.4 | v4 migration deferred (future work) |
| eslint | ^8 | hold ^8 (flat-config migration = future work) | |
| radix-ui pkgs | various | latest | low risk |
| react-photo-album | ^2.3 | latest **2.x only** | v3 breaking — don't jump |
| socket.io-client | ^4.7 | ^4 latest | |
| others (axios, react-hook-form, zod, …) | — | latest non-major | zod 3→4 only if @hookform/resolvers pair supports it trivially |
| Node (build) | — | **22 LTS** | |

## 4. Breaking-change work items (backend)

### 4.1 diffusers 0.27.2 → 0.39.0
Vendored: `model/brushnet/**`, `model/power_paint/**` (12 files, ~112 internal imports; most already post-0.26 paths). Fixes:
- `LoraLoaderMixin` → `StableDiffusionLoraLoaderMixin` / `StableDiffusionXLLoraLoaderMixin`.
- `diffusers.models.lora.adjust_lora_scale_text_encoder` — locate current home, update import.
- `from_single_file` call sites (`sd.py`, `sdxl.py`, `controlnet.py`, `download.py`, brushnet/powerpaint wrappers): `original_config_file` → `original_config`.
- **`[r2]` Safety-checker semantics MUST be preserved.** Current wrappers pass user-controlled `load_safety_checker=bool(disable_nsfw)` — do NOT blanket-replace with `safety_checker=None` (that would permanently disable screening). diffusers 0.39 still honors the deprecated arg by loading legacy safety components when true (`loaders/single_file.py:2260`); replace with the recommended pattern **keeping both branches**: enabled → explicitly load `StableDiffusionSafetyChecker` + feature extractor; disabled → `safety_checker=None`. Add a regression test asserting the enabled branch actually attaches a checker.
- `callback` → `callback_on_step_end` migration for upstream-pipeline call sites (`sd.py`/`sdxl.py`); vendored pipelines keep their internal style.
- Verify still-shipped legacy imports at build time: `StableDiffusionMixin`, `KarrasDiffusionSchedulers`, safety_checker module, Kandinsky2.2/PBE/Pix2Pix pipelines.

Fallback: if 0.39 breaks vendored pipelines beyond reasonable effort, bisect highest working pin (0.35/0.33/0.31) and record why. Erase models (LaMa etc.) never touch diffusers and must never regress.

### 4.2 transformers 4 → 5
- PyTorch-only: fine. `use_auth_token` → `token`: **`[r2]` usage EXISTS in `scripts/tool.py:86`** (plus removed `resume_download`, per-call `proxies` at `tool.py:99`) — migrate or delete that script explicitly.
- **dtype default "auto"**: audit every model/pipeline load to pass explicit `torch_dtype`/`dtype` (wrappers already route `get_torch_dtype` — verify coverage incl. vendored text encoders).
- **`[r2]` AnyText: explicit port required (BLOCKING, own subtask P2b).** `anytext/ldm/modules/encoders/modules.py:219,263` reaches into `CLIPTextModel.text_model` and calls encoder layers with the transformers-4 signature; transformers 5.14 restructures these internals and the encoder call contract. Work item: port `FrozenCLIPEmbedderT3` (and related) to the transformers-5 API against `openai/clip-vit-large-patch14`; verify OCR recognizer path (`cldm/recognizer.py`) unaffected. **Gate**: `test_anytext.py` passes on GPU. **Fallback if port stalls**: feature-gate AnyText (lazy import; model stays listed but raises a clear "not yet supported in 2.x, use 1.6.0" error) — decided fallback, not silent breakage.
- safetensors-only saving: no impact (we don't save HF checkpoints).

### 4.3 huggingface_hub 0.25 → 1.x
- **`[r2]` The brittle `requests`-era handling lives in `model/utils.py:980`** (string-matching error messages), not download.py — replace with typed hub exceptions (`GatedRepoError`, `RepositoryNotFoundError`, `LocalEntryNotFoundError`, …).
- Drop removed kwargs at all call sites (`local_dir_use_symlinks`, `resume_download`, `legacy_cache_layout`) — includes `scripts/tool.py`.
- `huggingface-cli` → `hf` (docs only). hf_xet: free.

### 4.4 torch ≥2.6 `torch.load` `weights_only=True` default
Audit ~20 call sites (`helper.py`, plugins gfpgan/realesrgan/facexlib/briarmbg/SAM/SAM2, anytext ldm/cldm/recognizer, **`[r2]` plus `scripts/tool.py:265`**).
- `[r2]` Policy: **try `weights_only=True` first everywhere** — the AnyText ldm/cldm call sites consume state-dict-shaped mappings and are expected to pass. Use `weights_only=False` ONLY where a specific pinned-URL checkpoint verifiably needs pickle, with an inline comment naming the file.
- `torch.jit.load` (LaMa & jit models) unaffected.

### 4.5 Pillow 9.5 → 11.x
- `anytext/utils.py:69`: port **both** removed calls — `font.getsize` → `getbbox`/`getlength` AND `font.getoffset` (removed in Pillow 10; getbbox output already includes the offset — rewrite the width/height/offset math accordingly) `[r2]`.
- Tree-wide grep for other removed APIs (`getsize`, `getoffset`, `ANTIALIAS`, `Image.LINEAR`).
- piexif × Pillow 11: covered by `test_save_exif.py`.

### 4.6 gradio 4.21 → 6.x (web_config only)
- Move to extra `iopaint[web-config]`, lazy import with clear install hint; port `web_config.py` to gradio 6 API.

### 4.7 Python 3.13
- `helper.py`: `imghdr` (removed 3.13) → Pillow-based format sniffing.
- `[r2]` CI matrix includes 3.13 (it's advertised, so it's gated).

### 4.8 numpy 2.x
- `[r2]` Fix known breaks (§2 numpy row: `np.int0` × 4 in AnyText). Then full grep for `np.float`/`np.int`/`np.bool`/`np.object`/`np.int0`/`np.uint0` across `iopaint/` and `scripts/`, including vendored plugin dirs.

### 4.9 Legacy entry points `[r2]`
- `iopaint/installer.py` (`install-plugins-packages`): update pins (onnxruntime>=1.20, rembg>=2.0.78) — keep CLI working.
- `build_docker.sh`: still clones/tags `lama-cleaner` — rewrite for the fork.
- `scripts/user_scripts/win_setup.bat` (+ friends): pins torch 2.1/cu118 and installs upstream package — replace with the new uv bootstrap (§6.3) or delete.

## 5. Improvements (strict upgrades, model lineup unchanged)

### 5.1 Interactive segmentation: SAM3 (transformers-native)
- `[r2]` Split by prompt type — they are NOT interchangeable:
  - **Click flow (existing UX)**: add `sam3` choice to `--interactive-seg-model` backed by **`Sam3Tracker`** (accepts point prompts → fits current `schema.py:451` request shape and `interactive_seg.py` plugin contract). Vendored SAM1/SAM2 choices untouched.
  - **Text flow (new, stretch)**: `Sam3` / **SAM3-LiteText** accept text/box — NOT click-compatible. Requires a new request schema + endpoint (`POST /api/v1/segment_by_text`) + minimal frontend input. Implemented only in P4 after click-parity lands; LiteText is never offered as a click model.
- `[r2]` `facebook/sam3*` repos are **gated on HF** — document required `hf auth login` + license acceptance in README and raise a friendly error on 401/403.

### 5.2 RemoveBG / BiRefNet `[r2]` (recast)
BiRefNet model IDs already exist in `schema.py`/`remove_bg.py`. Work = bump rembg ≥2.0.78 + onnxruntime ≥1.20, run `test_plugins.py` BiRefNet params as regression, and decide provider policy: keep CPU EP default; add optional `onnxruntime-gpu` note in docs (current `new_session` passes no providers — leave default, document).

### 5.5 Future work (evaluated, deferred): NVIDIA LocateAnything-3B
Text→bounding-box grounding VLM (Eagle family, 2026-05). Evaluated as a front-end for complex referring expressions ("the person on the left in red") that SAM3's short-noun-phrase prompts can't express: LocateAnything box → Sam3Tracker mask. Deferred because: (a) outputs boxes not masks (still needs SAM downstream), (b) 3B VLM footprint, (c) **NVIDIA non-commercial license + Qwen Research license — cannot ship in the distributed default**. If added later: opt-in local plugin only. Priority: SAM3 > BiRefNet > LocateAnything.

### 5.6 Dev ergonomics
- `ruff` (lint only; `E,F,I`), vendored dirs excluded from lint AND from any reformat.
- `uv pip compile` lockfile-style constraints for reproducible dev env.

## 6. Packaging & distribution

### 6.1 pyproject.toml (replaces setup.py)
- PEP 621, setuptools backend. `requires-python = ">=3.10,<3.14"` `[r2]` (tested-support policy, §2).
- Extras: `[plugins]` (rembg>=2.0.78, onnxruntime>=1.20), `[web-config]` (gradio>=6,<7), `[dev]`.
- `[r2]` Version single-sourcing: **introduce** `__version__ = "2.0.0.dev0"` in `iopaint/__init__.py` (does not exist today — setup.py hard-codes it) + `dynamic = ["version"]` via `setuptools.dynamic.attr`.
- `[r2]` Package data: translate setup.py's imperative glob of `iopaint/web_app/**` + yaml/txt configs into **declarative** `[tool.setuptools.package-data]` rules. Release gate inspects built **wheel AND sdist** for: JS/CSS assets, `anytext_sd15.yaml`, `ppocr_keys_v1.txt`, `original_sd_configs/*.yaml`.
- Keep `iopaint` console script name. Distribution name ≠ executable name: **placeholder `iopaint-ng`**, single grep-able constant, final name = owner decision before first publish.

### 6.2 CI & release (GitHub Actions)
- `[r2]` **`ci.yml` ships in Phase 1** and gates every later phase: ruff; pytest CPU subset (erase models, helpers, EXIF/ICC); frontend production build; **matrix = {ubuntu, windows} × {3.10, 3.12, 3.13}**, torch-cpu, Node 22; wheel+sdist build & clean-venv install smoke (`iopaint --help`, `iopaint start --model cv2` boot check).
- `release.yml` on tag: `[r2]` **separate build job → publish job**; publish consumes the already-tested artifact in a protected `pypi` environment with `id-token: write` only (PyPI trusted publisher configured for exact owner/repo/workflow/environment). **TestPyPI dry-run + `v2.0.0-rc1` before the real release.** GitHub Release gets wheel+sdist.
- GPU matrix (manual/self-hosted or dev-machine checklist): every retained diffusion family — see §8.

### 6.3 Install story
```bash
# recommended (uv, any platform; picks correct CUDA automatically on NVIDIA):
uv venv && uv pip install torch torchvision --torch-backend=auto
uv pip install iopaint-ng            # placeholder name
iopaint start --model lama
# one-shot trial:
uvx --from iopaint-ng iopaint start --model lama    # [r2] --from required (dist ≠ exe name)
```
- `[r2]` Windows bootstrap `scripts/install_windows.bat`: install uv → `uv venv` → `uv pip install torch torchvision --torch-backend=cu128` (Blackwell/Ada/Ampere) or `--torch-backend=auto`, **fail with a clear message if no CUDA-12.8-capable driver**; then install package; write `start.bat`. Deterministic — no silent CPU fallback for GPU machines.
- Docker: `nvidia/cuda:12.8-runtime-ubuntu24.04` + py3.12 (GPU), `python:3.12-slim` (CPU); multi-stage frontend build; replace `build_docker.sh` `[r2]`.
- README rewrite: install matrix, HF auth note for SAM3, `hf` CLI rename.

### 6.4 Deferred
- PyInstaller/portable exe (bat+uv achieves the UX without multi-GB brittleness).

## 7. Implementation phases (Codex)

Branch `modernize-2026`; vendored dirs get minimal-diff compat fixes only.

- **P1 — Packaging + CI skeleton**: pyproject.toml (+`__version__`), delete setup.py, regenerate requirement mirrors + CI check, ruff config, `ci.yml` `[r2]`, update `installer.py` pins `[r2]`.
  ✅ Gate: CI green on {ubuntu, windows} × {3.10, 3.12, 3.13}; `pip install -e .` + `iopaint --help`; wheel/sdist contents inspected.
- **P2a — Backend compat (non-AnyText)**: torch.load audit → hf_hub 1.x (incl. `model/utils.py:980`, `scripts/tool.py`) → diffusers 0.39 (incl. safety-checker both-branch fix) → transformers dtype audit → Pillow/imghdr/numpy sweeps → gradio extra.
- **P2b — AnyText port + gate** `[r2]`: CLIP embedder port to transformers 5, np.int0, getsize/getoffset. Fallback = feature-gate with clear error (owner-visible decision, not silent).
  ✅ Gate (P2 combined) `[r2]`: CPU suite green AND **full GPU matrix — one 512px job per retained family: sd15, sd2, sdxl, controlnet, brushnet(sd+xl), powerpaint v1, powerpaint v2, anytext (or explicit gated-fallback), paint-by-example, pix2pix, kandinsky2.2** on the dev machine. No phase completion on partial matrix.
- **P3 — Frontend**: §3 bumps (vite ^8.1, plugin-react, react 19, zustand 5 + use-sync-external-store, remove recoil/@types/axios/plugin-react-swc), rebuild embedded web_app.
  ✅ Gate: `npm run build` clean; browser e2e lama erase; CI green.
- **P4 — Improvements**: SAM3 click-parity via Sam3Tracker; rembg/onnxruntime regression (BiRefNet params); text-segment endpoint (stretch).
  ✅ Gate: plugin switch + segment round-trip on GPU; gated-repo error path tested logged-out.
- **P5 — Distribution**: `release.yml` (build/publish split, trusted publishing), Docker refresh, README + `install_windows.bat`, replace `build_docker.sh`/`win_setup.bat` `[r2]`, TestPyPI dry-run, tag `v2.0.0-rc1`.
  ✅ Gate: clean-venv wheel install runs on CPU env AND dev GPU env; TestPyPI install works.

Risk ranking: P2b (AnyText) > P2a-diffusers > P4-SAM3 > P3 > P1 ≈ P5.

## 8. Verification matrix

| Check | How | When |
|---|---|---|
| Erase models byte-compat | `test_model.py`, `test_model_md5.py` (CPU) | P1 CI onward |
| Diffusion families | GPU: one 512px job EACH retained family (list in §7 P2 gate) `[r2]` | end of P2 |
| Safety-checker branches | new regression test: enabled→checker attached; disabled→None `[r2]` | P2a |
| AnyText | `test_anytext.py` GPU, or explicit fallback gate `[r2]` | P2b |
| Plugins | `test_plugins.py` (incl. BiRefNet params) + SAM3 manual | P2/P4 |
| API + frontend | `iopaint start --model lama` → browser e2e | P3 |
| EXIF/ICC/quality | existing tests | CI |
| Packaging | wheel+sdist content inspection; clean-venv install; TestPyPI | P1/P5 |
| Windows bat | run on dev machine | P5 |

## 9. Open questions for owner (defaults chosen, non-blocking until P5 publish)

1. PyPI distribution name (placeholder `iopaint-ng`; publish blocked until confirmed).
2. AnyText: if the transformers-5 port stalls, accept feature-gate fallback? (default: yes, with clear error message).
3. Tailwind 4 / eslint 9 flat / React Compiler: deferred (agreed).
