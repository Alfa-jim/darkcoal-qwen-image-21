# Validation evidence

This file distinguishes local CPU evidence, published-container evidence and GPU
inference. It is updated with actual results before the handoff.

## Local checks

2026-10-12: `python -m unittest discover -s tests -v` passed **28 tests** on
Windows/Python 3.11.16/Pillow 12.3.0. The tests use tiny synthetic images/download
fixtures and a local HTTP engine simulator; they do not execute the image model.
The embedded CPU bootstrap matches the installer/model lock and compiles;
`python -m compileall` and staged `git diff --check` also passed.

An independent read-only review found no remaining major issues after correcting
CPU smoke checks to load the CUDA driver stub only in the help subprocess.
A download regression test demonstrated and fixed partial-data loss on repeated
early EOF; the installer now preserves that partial for a later resume.

## Container and publication

2026-10-12: [GitHub Actions run #1](https://github.com/Alfa-jim/darkcoal-qwen-image-21/actions/runs/38202873602)
completed successfully. Linux/Python 3.12 tests passed, all 394 native build steps
completed, Docker build-time CPU smoke checks passed, and a separate final-runtime
container smoke check passed before GHCR publication.

Built source commit: `d7d83cc6d41ceb17854eebff01e7e7a41dc85265`.
Engine source: `2988060a4338a5dcd94721c964a8e87003c1ac8b` (CUDA 12.8, sm86/sm89).
Public image:

```text
ghcr.io/alfa-jim/darkcoal-qwen-image-21@sha256:b430f7bccc84365916936b5510b8167e7e30ec21dac8078778c3c5432fcf185d
```

Anonymous manifest/config access and SHA256 verification passed for both
`latest` and `sha-d7d83cc6d41ceb17854eebff01e7e7a41dc85265`, pointing to the same
digest. Registry config confirms `linux/amd64`. Compressed layers total
2,342,020,807 bytes (2.34 GB). This is registry metadata verification; a full local
image pull was not performed. The local Docker Desktop engine could not be restored,
so container execution was verified on the GitHub Linux runner instead.

All four pinned Hugging Face URLs responded to public HEAD requests with status
200 and their exact expected byte sizes. No production model weights were
downloaded locally; downloader integrity/resume tests used tiny HTTP fixtures.

## GPU acceptance

Not performed: no RunPod endpoint, API key, prepared volume or GPU was supplied.
Required checks on L40S 48 GB: zero/one/ten references, consecutive requests,
RGBA output, execution latency, host RAM and peak VRAM. Ten-reference compatibility
with these exact Q4 files is an acceptance target, not a measured result.
