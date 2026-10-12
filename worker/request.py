"""Validate the public input and construct the pinned native engine request."""

import base64
import binascii
import io
import warnings

from PIL import Image, UnidentifiedImageError

SIGMAS = [1.0, .978453, .95418, .926626, .89508, .845148, .704534, .414568, 0.0]
MAX_IMAGE_PIXELS = 20_000_000
MAX_ENCODED_BYTES = 18 * 1024 * 1024


def build_payload(value):
    if not isinstance(value, dict):
        raise ValueError('input must be an object')
    unknown = set(value) - {'prompt', 'images', 'width', 'height', 'seed'}
    if unknown:
        raise ValueError(f'Unsupported input fields: {", ".join(sorted(unknown))}. '
                         'Turbo sampling settings are fixed.')
    prompt = value.get('prompt')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16384:
        raise ValueError('prompt must be nonempty text, at most 16384 characters')
    dimensions = {}
    for key in ('width', 'height'):
        number = value.get(key, 1024)
        if type(number) is not int or not 256 <= number <= 2048 or number % 32:
            raise ValueError(f'{key} must be 256–2048 and divisible by 32')
        dimensions[key] = number
    seed = value.get('seed', -1)
    if type(seed) is not int or not -1 <= seed <= 2**63 - 1:
        raise ValueError('seed must be -1 or a nonnegative signed 64-bit integer')
    images = value.get('images', [])
    if not isinstance(images, list) or len(images) > 10:
        raise ValueError('images must be a list of at most 10 references')
    refs, names, total = [], set(), 0
    for index, item in enumerate(images):
        label = f'images[{index}]'
        if not isinstance(item, dict):
            raise ValueError(f'{label} must contain name and image')
        name = item.get('name')
        if not isinstance(name, str) or not name or len(name) > 255 or name in names:
            raise ValueError(f'{label}.name must be nonempty and unique (max 255 characters)')
        names.add(name)
        encoded = item.get('image')
        if not isinstance(encoded, str) or not encoded:
            raise ValueError(f'{label}.image must be base64 or an image data URI')
        if encoded.startswith('data:'):
            prefix, separator, encoded = encoded.partition(',')
            if not separator or not prefix.startswith('data:image/') or not prefix.endswith(';base64'):
                raise ValueError(f'{label}.image has an invalid data URI')
        total += len(encoded)
        if total > MAX_ENCODED_BYTES:
            raise ValueError('Encoded references exceed 18 MiB; resize/compress them before submitting')
        try:
            raw = base64.b64decode(encoded, validate=True)
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format not in ('PNG', 'JPEG', 'WEBP'):
                        raise ValueError('Supported reference image formats: PNG, JPEG, WebP')
                    if image.width * image.height > MAX_IMAGE_PIXELS:
                        raise ValueError('Reference image exceeds 20 megapixels; resize it first')
                    image.verify()
                # verify() alone does not decode every pixel of a truncated JPEG.
                with Image.open(io.BytesIO(raw)) as image:
                    image.load()
        except (binascii.Error, OSError, UnidentifiedImageError,
                Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValueError(f'{label}.image is not a valid PNG, JPEG or WebP image') from exc
        refs.append(encoded)
    return {
        'prompt': prompt, **dimensions, 'seed': seed, 'batch_count': 1,
        'ref_images': refs, 'output_format': 'png', 'embed_image_metadata': False,
        'preview': 'none', 'hires': {'enabled': False},
        'sample_params': {
            'sample_steps': 8, 'sample_method': 'euler',
            'custom_sigmas': list(SIGMAS), 'flow_shift': 1.0,
            'guidance': {'txt_cfg': 1.0, 'distilled_guidance': 1.0},
        },
    }
