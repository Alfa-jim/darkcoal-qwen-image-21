"""Check the prepared volume against the immutable model lock."""

import hashlib
import json
from pathlib import Path


def load_manifest():
    return json.loads((Path(__file__).resolve().parents[1] / 'model-lock.json').read_text())


def validate_models(volume_root, manifest=None, verify_hashes=False):
    manifest = manifest if manifest is not None else load_manifest()
    root = Path(volume_root) / manifest['model_subdir']
    paths = {}
    for asset in manifest['assets']:
        path = root / asset['path']
        if not path.is_file():
            raise RuntimeError(f'Missing model: {path}. Attach the prepared network volume '
                               'and run the CPU download command in README.md.')
        if path.stat().st_size != asset['size']:
            raise RuntimeError(f'Wrong model size: {path}; expected {asset["size"]} bytes')
        if verify_hashes:
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != asset['sha256']:
                raise RuntimeError(f'Model checksum mismatch: {path}')
        paths[asset['role']] = path
    installed = root / 'model-manifest.json'
    try:
        if json.loads(installed.read_text()) != manifest:
            raise RuntimeError('Prepared model manifest differs from this worker; rerun the downloader')
    except (OSError, ValueError) as exc:
        raise RuntimeError(f'Missing or invalid model manifest: {installed}; rerun the downloader') from exc
    return paths
