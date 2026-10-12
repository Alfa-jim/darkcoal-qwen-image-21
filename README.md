# darkcoal-qwen-image-21

Native RunPod Serverless worker for **Qwen Image 2.1 Turbo** using the AtomicChat
**AD-Q4_K denoiser and abliterated AD-Q4_K encoder**. Supports text generation,
editing/composition with **0–10 ordered reference images**, and PNG alpha output.
The private inference engine stays loaded between jobs. All weights live on a
network volume; none are downloaded at worker startup or baked into the image.

Published public container: `ghcr.io/alfa-jim/darkcoal-qwen-image-21:latest`.
Verified immutable image:

```text
ghcr.io/alfa-jim/darkcoal-qwen-image-21@sha256:b430f7bccc84365916936b5510b8167e7e30ec21dac8078778c3c5432fcf185d
```

Build and CPU container checks passed. GPU inference is not yet tested; see
`docs/VALIDATION.md` for the exact evidence.

This worker accepts prompt/image requests, rather than ComfyUI workflow JSON.
It uses the same `output.images` base64 response shape as the adjacent workers.

## 1. Prepare models on a CPU Pod

Create a **30 GB network volume** in a datacenter with the GPU you intend to use.
Deploy a current Ubuntu 24.04 CPU Pod **with that network volume selected during
deployment**. A normal Pod volume disk is not the persistent network volume.
Its mount is normally `/workspace`.

**Paste the entire contents of [DOWNLOAD_ON_CPU_POD.sh](DOWNLOAD_ON_CPU_POD.sh)
into the Pod terminal.** This command is self-contained: no GitHub clone, GPU,
PyTorch, HF CLI, or Hugging Face login is needed. It includes the installer and
pinned manifest. Downloads total **11.32 GB** (10.55 GiB). Rerunning resumes
interrupted `.part` files and verifies all completed files with SHA256.

Or paste this short command, pinned to the tested release:

```bash
curl -fL --retry 3 https://raw.githubusercontent.com/Alfa-jim/darkcoal-qwen-image-21/d7d83cc6d41ceb17854eebff01e7e7a41dc85265/DOWNLOAD_ON_CPU_POD.sh -o /tmp/qwen21-models.sh && bash /tmp/qwen21-models.sh
```

For a different configured mount, set this before pasting:

```bash
export MODEL_VOLUME_ROOT=/your/network-volume-mount
```

The command refuses to download to an unmounted directory. It cannot distinguish
a network volume from a Pod's ordinary mounted volume disk, so confirm the
network volume was selected in the RunPod deployment UI. RunPod mounts the disk;
the command populates it. No manual `mount` command or copy is needed later.

If you already cloned the repository, the equivalent command is:

```bash
python3 scripts/download_models.py --volume-root /workspace
```

Weights are pinned to revisions, sizes and hashes in `model-lock.json`:

| Role | File | Approximate size |
| --- | --- | --- |
| Denoiser | `Qwen-Image-2.1-Turbo-AD-Q4_K.gguf` | 4.20 GB |
| Encoder | `Qwen-Image-2.1-Turbo-Abliterated-Uncensored-AD-Q4_K.gguf` | 5.29 GB |
| Vision | `mmproj-Qwen-Image-2.1-Turbo-Abliterated-Uncensored-F16.gguf` | 1.16 GB |
| VAE | `qwen_image_2.1_vae_bf16.safetensors` | 0.68 GB |

These are separate components: the denoiser generates the image, the encoder
interprets the prompt, the mmproj processes reference images, and the VAE converts
the model's output into pixels. Only the denoiser and encoder are AD-Q4_K. Build
logs list other quantization kernels because the engine supports multiple formats;
the installer does not download alternative Q6 or Q8 models. The AD-Q4_K layout
also retains higher precision for selected tensors inside those two files.

The requested “Uncensored” repository contains the encoder/projector, not the
image denoiser. That denoiser comes from AtomicChat's companion Turbo repository.
This native GGUF setup needs no separate VL adapter. Do not substitute the older
Qwen Image / Wan VAE. Source weights and caches stay beneath
`/workspace/models/qwen-image-21/`. A completion manifest is written only when all
assets pass verification. After preparation you can terminate the CPU Pod while
keeping the network volume.

## 2. Configure RunPod Serverless

| Setting | Value |
| --- | --- |
| Image | `ghcr.io/alfa-jim/darkcoal-qwen-image-21:latest`, preferably a verified digest |
| GPU | **L40S 48 GB** or RTX 6000 Ada 48 GB; Ampere sm86 is also compiled |
| CUDA | Host compatible with CUDA **12.8** (native Linux driver 570+ preferred) |
| Container disk | 20 GB starting allocation; increase if required by the published image size |
| Host RAM | 32 GB minimum starting target; 64 GB preferred for offloading |
| Network volume | Attach the same prepared volume; Serverless mounts it at `/runpod-volume` |
| Active workers | 0 for scale to zero; 1 if you want to avoid repeated cold starts |
| Maximum workers | Start at 1; increase after testing |
| Execution timeout | 1200 seconds; native generation timeout is 900 seconds |
| Public HTTP ports | None required; engine listens only on localhost |

Network-volume location constrains GPU availability. CUDA kernels in this build
target sm86/sm89; a Blackwell GPU requires a deliberate architecture/toolkit
build change, rather than using this image without checking compatibility.

Startup checks the mounted volume, exact asset sizes and completion manifest
before loading CUDA weights and registering the handler. Set
`VERIFY_MODEL_HASHES=1` for full startup checksum verification (reads all 11.32 GB
and increases cold-start time). Normal boots rely on the downloader's completed
checksum verification plus size/manifest checks.

Additional settings: `MODEL_VOLUME_ROOT` (default `/runpod-volume`),
`ENGINE_START_TIMEOUT` (300), `JOB_TIMEOUT_SECONDS` (900), `ENGINE_PORT` (1234).
The engine enables diffusion Flash Attention and CPU offloading. No concurrent
generations share a worker. On engine failure or timeout, its process is stopped
and reloaded for the next request.

## 3. Submit requests

### Browser playground

Open `playground.html` locally, or double-click `OPEN_PLAYGROUND.cmd` on Windows
(Python required). For a stable local origin on any platform:

```bash
python -m http.server 8765 --bind 127.0.0.1
```

Then open <http://127.0.0.1:8765/playground.html>. Use the same address each time
to keep your saved settings. Enter your RunPod endpoint URL (or ID) and API key.
They are saved in this browser's local storage, along with your prompt, size and
seed. The key stays masked until you reveal it; **Forget key** removes its saved
value. This is a personal local tool: do not enter your key on somebody else's
hosted copy. There are no third-party scripts or analytics.

Upload up to ten PNG/JPEG/WebP pictures, then write, for example:

```text
@picture1 is the character. Follow @picture 2's pose.
```

Click a reference label to insert it, or type `@` for suggestions. The playground
translates mentions into `Picture 1`, `Picture 2`, etc. using the current upload
order. Labels stay stable when you remove an image; missing mentions block
submission. The **Prompt sent to the model** disclosure shows the translation.
References are oriented and resized to at most 1024 px per side, keeping alpha
as PNG and compressing opaque images as JPEG. They remain in memory only and
must be uploaded again after a refresh. Requests are capped below the `/run`
payload limit. Turbo's eight Euler steps, CFG 1 and sigma schedule are fixed by
the worker; change only size and seed in the playground.

Generation uses asynchronous `/run` plus `/status/{id}` polling and offers
`/cancel/{id}`. The job ID and endpoint are saved so **Resume status check** can
restore the live elapsed timer after a refresh. Timing starts when you click
Generate, includes upload/queue time, and freezes on completion or failure.
The final timing also shows RunPod's worker execution and queue durations when
provided. A saved job lets the status check
retrieve an existing job without charging for another submission. Refreshing
never automatically submits a generation. After a submission/network error,
check RunPod's Requests tab before trying another generation. Download outputs
as PNG; **Save request JSON** exports inputs without credentials. Output images
are not stored across refreshes. RunPod's async result retention is limited; save
your PNG promptly. See the [official request documentation](https://docs.runpod.io/serverless/endpoints/send-requests).

Helper and controller tests: `node --test tests/playground*.cjs` (Node 18+).

### API requests

Minimal request:

```json
{"input":{"prompt":"A neon sign reading DARKCOAL in the rain","width":1024,"height":1024,"seed":42}}
```

Optional `images`: an ordered array of `{ "name": "ref1.png", "image": "BASE64" }`.
PNG/JPEG/WebP and image data URIs are accepted. Names must be unique. References
are forwarded in the same order; refer to them as Picture 1, Picture 2, etc.
For transparency, use Qwen's recommended prompt:
`This is an RGBA image with transparency. <description>. The image has alpha channel and the background is transparent.`

Width/height must be 256–2048 and divisible by 32; defaults are 1024. Seed is -1
(random) or a nonnegative signed 64-bit integer. One output per request.
Turbo uses **8 steps, Euler, CFG 1 and its exact custom sigma schedule**. These
are fixed; `steps`, `cfg`, `workflow`, and other undeclared input keys are rejected.

Build an edit/composition request locally (Python 3.11+ and Pillow required):

```bash
python scripts/make_request.py --prompt "Use the person from Picture 1 and the outfit from Picture 2" \
  --images person.png outfit.png --seed 42 --out request.json
```

The helper accepts up to ten paths, preserves their order, applies EXIF
orientation, and reduces references to at most 1024 pixels per side. It keeps
alpha as PNG and compresses opaque images as JPEG. This changes input pixels;
submit your own base64 request if you need untouched originals.

RunPod documents payload limits of 10 MB for `/run` and 20 MB for `/runsync`.
Base64 adds roughly one third to the file size, so ten large references need
compression. The helper enforces a conservative `/run` budget. The handler also
rejects reference images above 20 megapixels or combined base64 above 18 MiB.
Ten-reference support does not guarantee that every resolution/input combination
fits 48 GB; test your actual images and inspect memory failures.

Asynchronous request (recommended):

```bash
export RUNPOD_API_KEY='your-key'
export RUNPOD_ENDPOINT_ID='your-endpoint-id'
curl --fail-with-body -sS "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/run" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' \
  --data-binary @request.json
# Poll the id returned above:
curl --fail-with-body -sS "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/status/JOB_ID" \
  -H "Authorization: Bearer $RUNPOD_API_KEY"
```

Or submit, poll and save outputs with:

```bash
python scripts/run_request.py --endpoint "$RUNPOD_ENDPOINT_ID" --input request.json
```

Synchronous request for jobs that finish within the platform's sync wait window:

```bash
curl --fail-with-body -sS "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' \
  --data-binary @test_input.json
```

If `/runsync` returns `IN_PROGRESS`, poll `/status/JOB_ID`. Worker output:

```json
{"images":[{"filename":"job-id_0.png","type":"base64","data":"iVBOR..."}]}
```

Failures return `{"error":"actionable explanation"}` and no images.
Native image inputs/results are passed in memory; there are no shared job image
files on the network volume. Engine result caches expire after ten minutes.

## Build and publish

The public repository uses GitHub Actions to test first, compile CUDA from pinned
source, smoke-test the final runtime on CPU, then publish to GHCR. Tags:
`latest` on main, `sha-<full-commit>` on every published commit, and `v*` releases.
No Hugging Face credentials or model downloads are used in CI.

Run `scripts/publish.ps1` in PowerShell after `gh auth login` to create the
repository, push the committed project, monitor CI and verify a public manifest.
GHCR packages may initially be private even when their repositories are public.
If anonymous pulls fail, open the package settings and change visibility to
Public, then rerun `scripts/verify_registry.py`.

Local Docker build:

```bash
docker build --platform linux/amd64 -t darkcoal-qwen-image-21:local .
docker run --rm --entrypoint python darkcoal-qwen-image-21:local scripts/smoke.py
docker run --rm --gpus all -v /path/to/network-volume:/runpod-volume:ro \
  -v "$(pwd)/test_input.json:/app/test_input.json:ro" \
  darkcoal-qwen-image-21:local
```

The last command is a one-shot GPU test: outside RunPod, the SDK reads the mounted
test request, runs it and exits. It does not start a public HTTP API.

CPU tests (tiny fixtures; no production weights):

```bash
python -m pip install Pillow==12.3.0
python -m unittest discover -s tests -v
python scripts/make_download_command.py --check
```

## Sources and licensing

- [Requested AtomicChat encoder/projector](https://huggingface.co/AtomicChat/Qwen-Image-2.1-Turbo-Uncensored-GGUF)
- [AtomicChat Turbo denoiser and sampling settings](https://huggingface.co/AtomicChat/Qwen-Image-2.1-Turbo-GGUF)
- [Qwen 2.1 VAE](https://huggingface.co/Comfy-Org/Qwen-Image-2.1)
- [Qwen 2.1 ten-reference capability](https://huggingface.co/Qwen/Qwen-Image-2.1)
- [Pinned stable-diffusion.cpp Qwen documentation](https://github.com/leejet/stable-diffusion.cpp/blob/2988060a4338a5dcd94721c964a8e87003c1ac8b/docs/qwen_image_2.1.md)
- [Pinned native server API](https://github.com/leejet/stable-diffusion.cpp/blob/2988060a4338a5dcd94721c964a8e87003c1ac8b/examples/server/api.md)
- [RunPod network volumes](https://docs.runpod.io/storage/network-volumes)
- [RunPod request limits and polling](https://docs.runpod.io/serverless/endpoints/operation-reference)

The image denoiser is distributed under the Qwen Research License; the modified
encoder/projector repository declares Apache-2.0, and stable-diffusion.cpp is MIT.
These components retain their own licenses. Publishing the worker does not
change the model license. AtomicChat reports no measured increase in uncensoring
of images from this encoder; do not interpret its name as a guarantee of output.
