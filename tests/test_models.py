import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from worker.models import validate_models


def fixture_manifest(data=b'GGUFfixture'):
    return {'schema_version': 1, 'model_subdir': 'models/qwen-image-21', 'assets': [
        {'role': 'denoiser', 'repo': 'fixture/model', 'revision': 'a' * 40,
         'source': 'model.gguf', 'path': 'diffusion_models/model.gguf',
         'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}]}


class ModelTests(unittest.TestCase):
    def test_missing_asset_and_completion_manifest_fail_clearly(self):
        manifest = fixture_manifest()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(RuntimeError, 'model'):
                validate_models(root, manifest)
            asset = root / manifest['model_subdir'] / manifest['assets'][0]['path']
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b'GGUFfixture')
            with self.assertRaisesRegex(RuntimeError, 'manifest'):
                validate_models(root, manifest)
            (root / manifest['model_subdir'] / 'model-manifest.json').write_text(json.dumps(manifest))
            self.assertEqual(validate_models(root, manifest)['denoiser'], asset)

    def test_size_and_optional_checksum_validation(self):
        manifest = fixture_manifest()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            asset = root / manifest['model_subdir'] / manifest['assets'][0]['path']
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b'X')
            (asset.parent.parent / 'model-manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError, 'size'):
                validate_models(root, manifest)
            asset.write_bytes(b'XXXXXXXXXXX')
            with self.assertRaisesRegex(RuntimeError, 'checksum'):
                validate_models(root, manifest, verify_hashes=True)

    def test_production_manifest_has_four_exact_model_roles(self):
        manifest = json.loads(Path('model-lock.json').read_text())
        self.assertEqual({x['role'] for x in manifest['assets']},
                         {'denoiser', 'encoder', 'vision', 'vae'})
        for asset in manifest['assets']:
            self.assertEqual(len(asset['sha256']), 64)
            self.assertEqual(len(asset['revision']), 40)
        for asset in manifest['assets'][:2]:
            self.assertIn('AD-Q4_K', asset['source'])
