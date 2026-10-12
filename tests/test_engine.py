import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from worker.engine import EngineClient, EngineError
from test_request import image_data


class FakeEngine(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path.endswith('/cancel'):
            self.server.cancelled = True
            self.send({'status': 'cancelled'})
        else:
            self.server.payload = body
            self.send({'id': 'job_123'}, 202)

    def do_GET(self):
        if self.path.endswith('capabilities'):
            self.send({'supported_modes': ['img_gen'],
                       'features_by_mode': {'img_gen': {'ref_images': True}}})
        elif self.server.mode == 'failed':
            self.send({'status': 'failed', 'error': {'message': 'CUDA out of memory'}})
        elif self.server.mode == 'pending':
            self.send({'status': 'generating'})
        else:
            self.send({'status': 'completed', 'result': {'images': [
                {'index': 0, 'b64_json': image_data()}]}})

    def send(self, value, code=200):
        data = json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), FakeEngine)
        self.server.mode = 'completed'
        self.server.cancelled = False
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = EngineClient(f'http://127.0.0.1:{self.server.server_port}',
                                   timeout=.1, poll_interval=.01)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_completed_job_matches_existing_response_contract(self):
        result = self.client.generate({'prompt': 'cat'}, 'rp-job')
        self.assertEqual(result['images'][0]['type'], 'base64')
        self.assertEqual(result['images'][0]['filename'], 'rp-job_0.png')
        self.assertEqual(result['images'][0]['data'], image_data())
        self.assertEqual(self.server.payload['prompt'], 'cat')

    def test_engine_failure_is_actionable(self):
        self.server.mode = 'failed'
        with self.assertRaisesRegex(EngineError, 'out of memory'):
            self.client.generate({'prompt': 'cat'}, 'rp-job')

    def test_timeout_cancels_native_job(self):
        self.server.mode = 'pending'
        with self.assertRaisesRegex(EngineError, 'timed out'):
            self.client.generate({'prompt': 'cat'}, 'rp-job')
        self.assertTrue(self.server.cancelled)

    def test_consecutive_jobs_and_recovery_after_failure(self):
        self.server.mode = 'failed'
        with self.assertRaises(EngineError):
            self.client.generate({}, 'first')
        self.server.mode = 'completed'
        for job_id in ('second', 'third'):
            self.assertTrue(self.client.generate({}, job_id)['images'])
