# Qwen Image 2.1 Q4 Implementation Plan

Goal: deployable model-free native worker plus verified network-volume installer.
Spec: docs/design.md. Stack: Python 3.12, RunPod SDK, Pillow, CUDA 12.8,
stable-diffusion.cpp pinned source, GitHub Actions and GHCR.

Global constraints: 0–10 ordered references, both main weights AD-Q4_K, fixed
eight-step Turbo schedule, one job per worker, no runtime model downloads.

Review focus: malformed images; timeout leaves generation running; download
resume accepts changed files; volume path accidentally points at container disk;
failed startup masquerades as a healthy worker.

## Task 1 — Request and engine contract
- [x] Write and run failing tests for validation, ordered references, exact sigma
  forwarding, output format, native failure, timeout cancellation and recovery.
- [x] Implement worker/request.py (build_payload), worker/engine.py (EngineClient)
  and handler.py (handler + startup). Test against a local fake HTTP engine.
- [x] Run unittest discovery; verify failures are actionable and cleanup occurs.

## Task 2 — Models and preparation
- [x] Write and run failing tests for missing assets, manifest hashes, resumed
  HTTP downloads, idempotence, incorrect ranges and corrupted files.
- [x] Implement model-lock.json, worker/models.py (validate_models), and
  scripts/download_models.py (prepare/download_file), with a standalone Bash
  bootstrap command generated from the same installer and lock manifest.
- [x] Verify tests use tiny fixtures and never download production weights.

## Task 3 — Runtime and release
- [x] Add startup supervision, pinned CUDA Docker build, dependencies, examples,
  native reference helper, documentation, build/test CI and publishing helper.
- [x] Run full tests, syntax checks, static container/CI checks, and final review.
- [ ] Commit the isolated project. Create public repository and push main;
  monitor GHCR build and verify public manifest and immutable digest.
- [ ] Report actual evidence and distinguish unavailable GPU checks.

Ruling: a new independent repository in the requested folder supplies isolation;
no existing repository or worktree is modified. The user's implementation request
approves writing the already reviewed design and implementation artifacts.
