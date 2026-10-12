#!/usr/bin/env python3
"""Standalone, dependency-free installer for an already attached network volume."""

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def asset_url(asset):
    return ('https://huggingface.co/' + asset['repo'] + '/resolve/'
            + asset['revision'] + '/' + quote(asset['source'], safe='/'))


def verified(path, asset):
    if not path.is_file() or path.stat().st_size != asset['size']:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == asset['sha256']


def download_file(url, destination, asset):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if verified(destination, asset):
            print(f'Already verified: {destination.name}', flush=True)
            return
        raise RuntimeError(f'Unverified existing file: {destination}. Move it aside before retrying; '
                           'the installer will not overwrite existing model files.')
    partial = destination.with_name(destination.name + '.part')
    for attempt in range(3):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset == asset['size']:
            break
        if offset > asset['size']:
            raise RuntimeError(f'Partial file larger than expected: {partial}; move it aside')
        headers = {'Range': f'bytes={offset}-'} if offset else {}
        try:
            with urlopen(Request(url, headers=headers), timeout=60) as response:
                if response.status == 206:
                    expected = f'bytes {offset}-{asset["size"] - 1}/{asset["size"]}'
                    if response.headers.get('Content-Range') != expected:
                        raise RuntimeError('Invalid HTTP range response; refusing to append mismatched bytes')
                    mode = 'ab'
                elif response.status == 200:
                    mode = 'wb'  # A server may ignore Range; never append a full response.
                    offset = 0
                else:
                    raise RuntimeError(f'Unexpected download status {response.status}')
                print(f'Downloading {destination.name} ({offset}/{asset["size"]} bytes)', flush=True)
                with partial.open(mode) as output:
                    downloaded, last_report = offset, time.monotonic()
                    while chunk := response.read(8 * 1024 * 1024):
                        downloaded += len(chunk)
                        if downloaded > asset['size']:
                            raise RuntimeError('Download exceeds the pinned file size')
                        output.write(chunk)
                        if time.monotonic() - last_report >= 15:
                            print(f'  {destination.name}: {downloaded / asset["size"]:.0%}', flush=True)
                            last_report = time.monotonic()
                    output.flush()
                    os.fsync(output.fileno())
            if partial.stat().st_size == asset['size']:
                break
        except (URLError, OSError) as exc:
            if attempt == 2:
                raise RuntimeError(f'Download interrupted; rerun to resume {partial}: {exc}') from exc
            print(f'Download interrupted, retrying: {exc}', flush=True)
        if attempt < 2:
            time.sleep(2**attempt)
    if not partial.exists() or partial.stat().st_size < asset['size']:
        raise RuntimeError(f'Download incomplete; rerun to resume {partial}')
    if not verified(partial, asset):
        # This file was created exclusively by this installer; a corrupt partial
        # cannot be resumed safely. Preserve existing finalized files above.
        partial.unlink(missing_ok=True)
        raise RuntimeError(f'Size/checksum verification failed for {destination.name}; rerun to download again')
    os.replace(partial, destination)
    print(f'SHA256 verified: {destination.name}', flush=True)


@contextlib.contextmanager
def download_lock(path):
    """OS-released advisory lock, including when an interrupted process dies."""
    with path.open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            if stream.tell() == 0:
                stream.write(b'\0')
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError('Another model download is already running on this volume') from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError('Another model download is already running on this volume') from exc
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def prepare(volume_root, manifest, allow_unmounted=False):
    volume_root = Path(volume_root).resolve()
    if not volume_root.is_dir() or (not allow_unmounted and not os.path.ismount(volume_root)):
        raise RuntimeError(f'{volume_root} is not an attached volume mount. '
                           'Attach your network volume when deploying the CPU Pod.')
    # Restrict every manifest path to this dedicated subtree before writing files.
    if manifest.get('model_subdir') != 'models/qwen-image-21' or manifest.get('schema_version') != 1:
        raise RuntimeError('Unsupported model manifest')
    root = volume_root / manifest['model_subdir']
    for asset in manifest['assets']:
        if not (root / asset['path']).resolve().is_relative_to(root.resolve()):
            raise RuntimeError('Model path escapes the dedicated model directory')
        if not re.fullmatch(r'[0-9a-f]{64}', asset['sha256']):
            raise RuntimeError('Invalid model checksum in manifest')
    root.mkdir(parents=True, exist_ok=True)
    cache = root / '.cache'
    cache.mkdir(exist_ok=True)
    with download_lock(cache / 'download.lock'):
        remaining = 0
        for asset in manifest['assets']:
            path = root / asset['path']
            if path.exists():
                continue  # download_file verifies finalized files before accepting them.
            partial = path.with_name(path.name + '.part')
            remaining += max(0, asset['size'] - (partial.stat().st_size if partial.exists() else 0))
        if shutil.disk_usage(volume_root).free < remaining + 512 * 1024 * 1024:
            raise RuntimeError(f'Not enough free volume space: need {remaining + 512 * 1024 * 1024} bytes')
        for asset in manifest['assets']:
            download_file(asset_url(asset), root / asset['path'], asset)
        staging = root / 'model-manifest.json.part'
        staging.write_text(json.dumps(manifest, indent=2) + '\n')
        os.replace(staging, root / 'model-manifest.json')
    print(f'All four production assets verified. Prepared model directory: {root}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--volume-root', default='/workspace')
    parser.add_argument('--manifest', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'model-lock.json')
    parser.add_argument('--allow-unmounted', action='store_true',
                        help='For local tests only; never use this to prepare a RunPod volume')
    args = parser.parse_args()
    try:
        prepare(Path(args.volume_root), json.loads(args.manifest.read_text()), args.allow_unmounted)
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')


if __name__ == '__main__':
    main()
