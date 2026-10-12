#!/usr/bin/env python3
"""Verify anonymous GHCR access, platform and immutable manifest digest."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPOSITORY = 'alfa-jim/darkcoal-qwen-image-21'


def verify(tag='latest'):
    token_url = 'https://ghcr.io/token?' + urlencode({
        'service': 'ghcr.io', 'scope': f'repository:{REPOSITORY}:pull'})
    with urlopen(token_url, timeout=30) as response:
        token = json.load(response)['token']
    headers = {'Authorization': 'Bearer ' + token, 'Accept': ', '.join([
        'application/vnd.oci.image.manifest.v1+json',
        'application/vnd.docker.distribution.manifest.v2+json'])}
    request = Request(f'https://ghcr.io/v2/{REPOSITORY}/manifests/{tag}', headers=headers)
    with urlopen(request, timeout=30) as response:
        raw = response.read()
        digest = response.headers.get('Docker-Content-Digest')
    computed = 'sha256:' + hashlib.sha256(raw).hexdigest()
    if digest != computed:
        raise RuntimeError('Registry manifest digest does not match the returned bytes')
    manifest = json.loads(raw)
    if 'config' not in manifest:
        raise RuntimeError('Expected the single-platform manifest produced by this build')
    config_digest = manifest['config']['digest']
    request = Request(f'https://ghcr.io/v2/{REPOSITORY}/blobs/{config_digest}', headers=headers)
    with urlopen(request, timeout=30) as response:
        config_raw = response.read()
    if 'sha256:' + hashlib.sha256(config_raw).hexdigest() != config_digest:
        raise RuntimeError('Registry config checksum mismatch')
    config = json.loads(config_raw)
    if config.get('os') != 'linux' or config.get('architecture') != 'amd64':
        raise RuntimeError('Published image is not linux/amd64')
    return {'image': f'ghcr.io/{REPOSITORY}@{digest}', 'tag': tag,
            'platform': 'linux/amd64', 'anonymous_pull': True,
            'compressed_layer_bytes': sum(layer['size'] for layer in manifest['layers'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', default='latest')
    parser.add_argument('--out', type=Path, default=Path('publication.json'))
    args = parser.parse_args()
    try:
        result = verify(args.tag)
    except Exception as exc:
        parser.exit(1, f'Public registry verification failed: {exc}\n'
                    'Check the build result, then set the GHCR package visibility to Public.\n')
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
