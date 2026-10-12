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

Not yet built/published. The Dockerfile includes CPU import and native-flag smoke
checks. GitHub Actions also runs these against the final runtime before pushing.

## GPU acceptance

Not performed: no RunPod endpoint, API key, prepared volume or GPU was supplied.
Required checks on L40S 48 GB: zero/one/ten references, consecutive requests,
RGBA output, execution latency, host RAM and peak VRAM. Ten-reference compatibility
with these exact Q4 files is an acceptance target, not a measured result.
