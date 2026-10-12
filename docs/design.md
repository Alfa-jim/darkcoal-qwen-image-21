# Qwen Image 2.1 Turbo Q4 worker

Approved design (2026-10-12): standalone RunPod queue worker using a persistent,
localhost-only stable-diffusion.cpp server. Both the AtomicChat Turbo denoiser and
abliterated Qwen3-VL encoder use AD-Q4_K. Matching F16 mmproj and BF16 Qwen 2.1 VAE
live exclusively on an attached network volume. No separate VL adapter is needed.

Input: prompt, optional ordered images [{name, image}] (base64/data URI, 0–10),
width/height (256–2048, multiples of 32, default 1024), seed (-1 or nonnegative).
Output: images [{filename, type: base64, data}]. One output and one active job per
worker. Turbo settings are fixed to eight Euler steps, CFG 1 and the published
sigma schedule. Preserve PNG alpha. No ComfyUI workflow compatibility.

Preparation: CPU-only, resumable downloads with pinned HF revisions, expected
sizes and SHA256, volume verification, download locking and atomic completion.
Use /workspace for Pod preparation, /runpod-volume for Serverless; a 30 GB volume
is recommended. The script populates an attached volume; RunPod mounts it.

Release: public Alfa-jim/darkcoal-qwen-image-21 repository and public GHCR package,
linux/amd64 CUDA image without model layers, CI tests and container smoke checks,
latest and commit-specific tags, registry digest verification. Target L40S 48 GB.

Acceptance: CPU unit/integration tests, downloader resume/integrity cases, CI
container build, then actual GPU generation with zero/one/ten references and
consecutive jobs on a supplied endpoint. Publication is not GPU validation.
The user rents preparation compute and configures the RunPod endpoint.
