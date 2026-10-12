import base64
import io
import unittest

from PIL import Image

from worker.request import build_payload


def image_data(color='red'):
    out = io.BytesIO()
    Image.new('RGBA', (32, 32), color).save(out, format='PNG')
    return base64.b64encode(out.getvalue()).decode()


class RequestTests(unittest.TestCase):
    def test_text_generation_uses_fixed_turbo_schedule(self):
        payload = build_payload({'prompt': 'a cat'})
        self.assertEqual(payload['ref_images'], [])
        self.assertEqual((payload['width'], payload['height']), (1024, 1024))
        self.assertEqual(payload['sample_params']['sample_steps'], 8)
        self.assertEqual(payload['sample_params']['sample_method'], 'euler')
        self.assertEqual(payload['sample_params']['guidance']['txt_cfg'], 1.0)
        self.assertEqual(payload['sample_params']['custom_sigmas'],
                         [1.0, .978453, .95418, .926626, .89508, .845148, .704534, .414568, 0.0])
        self.assertEqual(payload['output_format'], 'png')
        self.assertEqual(payload['batch_count'], 1)

    def test_ten_references_preserve_order_and_rgba(self):
        refs = [image_data((i * 20, 0, 0, 128)) for i in range(10)]
        payload = build_payload({'prompt': 'compose all images', 'images': [
            {'name': f'ref{i}.png', 'image': 'data:image/png;base64,' + ref}
            for i, ref in enumerate(refs)]})
        self.assertEqual(payload['ref_images'], refs)

    def test_one_reference(self):
        ref = image_data()
        self.assertEqual(build_payload({'prompt': 'edit', 'images': [
            {'name': 'a.png', 'image': ref}]})['ref_images'], [ref])

    def test_bad_input_is_rejected_before_inference(self):
        cases = [None, [], {}, {'prompt': ' '}, {'prompt': 3},
                 {'prompt': 'a', 'width': 257}, {'prompt': 'a', 'height': 2080},
                 {'prompt': 'a', 'width': True}, {'prompt': 'a', 'seed': -2},
                 {'prompt': 'a', 'seed': 1.5}, {'prompt': 'a', 'images': {}},
                 {'prompt': 'a', 'images': [None]},
                 {'prompt': 'a', 'images': [{'name': 'a', 'image': 'invalid'}]},
                 {'prompt': 'a', 'steps': 4}]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_payload(value)

    def test_eleven_references_rejected(self):
        with self.assertRaisesRegex(ValueError, '10'):
            build_payload({'prompt': 'a', 'images': [
                {'name': f'{i}.png', 'image': image_data()} for i in range(11)]})

    def test_duplicate_names_and_non_image_bytes_rejected(self):
        with self.assertRaises(ValueError):
            build_payload({'prompt': 'a', 'images': [
                {'name': 'x.png', 'image': image_data()}] * 2})
        with self.assertRaisesRegex(ValueError, 'image'):
            build_payload({'prompt': 'a', 'images': [{'name': 'x.png',
                'image': base64.b64encode(b'not an image').decode()}]})
