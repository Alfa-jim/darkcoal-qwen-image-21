#!/usr/bin/env python3
"""Build a request with ordered references, sized for RunPod payload limits."""

import argparse
import base64
import io
import json
from pathlib import Path
import sys

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worker.request import build_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--images', nargs='*', type=Path, default=[])
    parser.add_argument('--width', type=int, default=1024)
    parser.add_argument('--height', type=int, default=1024)
    parser.add_argument('--seed', type=int, default=-1)
    parser.add_argument('--out', type=Path, default=Path('request.json'))
    args = parser.parse_args()
    if len(args.images) > 10:
        parser.error('At most 10 reference images are supported')
    images = []
    for index, path in enumerate(args.images):
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original)
            image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            alpha = image.mode in ('RGBA', 'LA') or 'transparency' in image.info
            image = image.convert('RGBA' if alpha else 'RGB')
            if alpha:
                image.save(output, format='PNG', optimize=True)
            else:
                image.save(output, format='JPEG', quality=90, optimize=True)
            images.append({'name': f'ref{index + 1}.{"png" if alpha else "jpg"}',
                           'image': base64.b64encode(output.getvalue()).decode()})
    job_input = {'prompt': args.prompt, 'images': images, 'width': args.width,
                 'height': args.height, 'seed': args.seed}
    build_payload(job_input)
    request = json.dumps({'input': job_input}, ensure_ascii=False)
    if len(request.encode()) > 9_500_000:
        parser.error('Request is too large for /run; compress references further')
    args.out.write_text(request + '\n', encoding='utf-8')
    print(f'{args.out}: {len(images)} ordered references, {len(request.encode())} bytes')


if __name__ == '__main__':
    main()
