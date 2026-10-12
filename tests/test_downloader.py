import contextlib
import hashlib
import threading
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from scripts.download_models import download_file, prepare
from test_models import fixture_manifest

DATA = b'GGUF' + bytes(range(256)) * 40


class FileServer(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.hits += 1
        requested = self.headers.get('Range')
        self.server.ranges.append(requested)
        offset = int(requested.split('=')[1].split('-')[0]) if requested else 0
        if self.server.mode == 'ignore-range':
            offset = 0
        data = DATA[offset:]
        if self.server.mode == 'early-eof':
            data = data[:max(1, len(data) // 2)]
        self.send_response(206 if offset else 200)
        if offset:
            start = offset + 1 if self.server.mode == 'bad-range' else offset
            self.send_header('Content-Range', f'bytes {start}-{len(DATA)-1}/{len(DATA)}')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), FileServer)
        self.server.hits, self.server.ranges, self.server.mode = 0, [], 'normal'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.temp = tempfile.TemporaryDirectory()
        self.dest = Path(self.temp.name) / 'model.gguf'
        self.url = f'http://127.0.0.1:{self.server.server_port}/model.gguf'
        self.asset = {'size': len(DATA), 'sha256': hashlib.sha256(DATA).hexdigest()}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_atomic_download_and_idempotent_rerun(self):
        download_file(self.url, self.dest, self.asset)
        self.assertEqual(self.dest.read_bytes(), DATA)
        self.assertFalse(self.dest.with_name(self.dest.name + '.part').exists())
        download_file(self.url, self.dest, self.asset)
        self.assertEqual(self.server.hits, 1)

    def test_resume_partial_file_with_range(self):
        self.dest.with_name(self.dest.name + '.part').write_bytes(DATA[:100])
        download_file(self.url, self.dest, self.asset)
        self.assertEqual(self.server.ranges, ['bytes=100-'])
        self.assertEqual(self.dest.read_bytes(), DATA)

    def test_server_ignoring_range_restarts_download(self):
        self.server.mode = 'ignore-range'
        self.dest.with_name(self.dest.name + '.part').write_bytes(DATA[:100])
        download_file(self.url, self.dest, self.asset)
        self.assertEqual(self.dest.read_bytes(), DATA)

    def test_invalid_range_or_checksum_never_promoted(self):
        self.server.mode = 'bad-range'
        self.dest.with_name(self.dest.name + '.part').write_bytes(DATA[:100])
        with self.assertRaisesRegex(RuntimeError, 'range'):
            download_file(self.url, self.dest, self.asset)
        self.assertFalse(self.dest.exists())
        self.server.mode = 'normal'
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            download_file(self.url, self.dest, {**self.asset, 'sha256': '0' * 64})
        self.assertFalse(self.dest.exists())

    def test_existing_corrupted_file_not_overwritten(self):
        self.dest.write_bytes(b'wrong')
        with self.assertRaisesRegex(RuntimeError, 'existing'):
            download_file(self.url, self.dest, self.asset)
        self.assertEqual(self.dest.read_bytes(), b'wrong')

    def test_repeated_early_eof_preserves_partial_for_later_resume(self):
        self.server.mode = 'early-eof'
        partial = self.dest.with_name(self.dest.name + '.part')
        with patch('scripts.download_models.time.sleep'):
            with self.assertRaisesRegex(RuntimeError, 'resume'):
                download_file(self.url, self.dest, self.asset)
        self.assertTrue(partial.is_file())
        self.assertGreater(partial.stat().st_size, 0)
        self.assertLess(partial.stat().st_size, len(DATA))
        self.server.mode = 'normal'
        download_file(self.url, self.dest, self.asset)
        self.assertEqual(self.dest.read_bytes(), DATA)

    def test_prepare_refuses_unmounted_path(self):
        with patch('os.path.ismount', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'mount'):
                prepare(Path(self.temp.name), fixture_manifest())

    def test_prepare_installs_manifest_only_after_success(self):
        manifest = fixture_manifest(DATA)
        with patch('scripts.download_models.asset_url', return_value=self.url):
            prepare(Path(self.temp.name), manifest, allow_unmounted=True)
        self.assertTrue((Path(self.temp.name) / manifest['model_subdir'] / 'model-manifest.json').is_file())
