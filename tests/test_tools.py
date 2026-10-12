import base64
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from scripts.make_download_command import make_command
from worker.request import build_payload


class ToolTests(unittest.TestCase):
    def test_self_contained_cpu_command_compiles_and_refuses_unmounted_path(self):
        command = make_command()
        self.assertEqual(Path('DOWNLOAD_ON_CPU_POD.sh').read_text(), command)
        body = command.split("python3 - <<'QWEN21_BOOTSTRAP'\n", 1)[1].rsplit('\nQWEN21_BOOTSTRAP', 1)[0]
        with patch('os.path.ismount', return_value=False):
            with self.assertRaisesRegex(SystemExit, 'network-volume mount'):
                exec(compile(body, 'bootstrap', 'exec'), {})

    def test_reference_helper_preserves_order_and_alpha_at_bounded_resolution(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = []
            for index, color in enumerate(('red', 'blue')):
                path = root / f'{index}.png'
                Image.new('RGBA', (2048, 1024), color).save(path)
                paths.append(str(path))
            out = root / 'request.json'
            subprocess.run([sys.executable, 'scripts/make_request.py', '--prompt', 'compose',
                            '--images', *paths, '--out', str(out)], check=True, capture_output=True)
            request = json.loads(out.read_text())['input']
            build_payload(request)
            for item, color in zip(request['images'], ((255, 0, 0, 255), (0, 0, 255, 255))):
                with Image.open(io.BytesIO(base64.b64decode(item['image']))) as image:
                    self.assertEqual(image.size, (1024, 512))
                    self.assertEqual(image.mode, 'RGBA')
                    self.assertEqual(image.getpixel((0, 0)), color)
