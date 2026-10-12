"""Small client for the pinned sd-server native async image API."""

import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class EngineError(RuntimeError):
    """An engine job failed; the runtime recycles the engine before another job."""


class EngineClient:
    def __init__(self, base_url='http://127.0.0.1:1234', timeout=900, poll_interval=.5):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.poll_interval = poll_interval

    def request(self, method, path, body=None, timeout=15):
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base_url + path, data=data, method=method,
                      headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read(4096).decode(errors='replace')
            raise EngineError(f'Engine HTTP {exc.code}: {detail}') from exc
        except (URLError, OSError, ValueError) as exc:
            raise EngineError(f'Engine unavailable or returned invalid JSON: {exc}') from exc

    def capabilities(self):
        return self.request('GET', '/sdcpp/v1/capabilities')

    def generate(self, payload, runpod_job_id):
        deadline = time.monotonic() + self.timeout
        native_id = None
        terminal = False
        try:
            accepted = self.request('POST', '/sdcpp/v1/img_gen', payload,
                                    timeout=min(30, self.timeout))
            native_id = accepted.get('id') if isinstance(accepted, dict) else None
            if not isinstance(native_id, str) or not native_id:
                raise EngineError('Engine did not return a generation job id')
            path = '/sdcpp/v1/jobs/' + quote(native_id, safe='')
            while time.monotonic() < deadline:
                state = self.request('GET', path,
                                     timeout=max(.01, min(15, deadline - time.monotonic())))
                if not isinstance(state, dict):
                    raise EngineError('Engine returned an invalid job status')
                status = state.get('status')
                if status == 'completed':
                    terminal = True
                    result = state.get('result') or {}
                    images = result.get('images') if isinstance(result, dict) else None
                    if not isinstance(images, list) or len(images) != 1:
                        raise EngineError('Engine completed without exactly one output image')
                    data = images[0].get('b64_json') if isinstance(images[0], dict) else None
                    if not isinstance(data, str) or not data:
                        raise EngineError('Engine returned an empty image')
                    safe_id = re.sub(r'[^A-Za-z0-9_-]', '_', str(runpod_job_id))[:100] or 'image'
                    return {'images': [{'filename': safe_id + '_0.png',
                                        'type': 'base64', 'data': data}]}
                if status in ('failed', 'cancelled'):
                    terminal = True
                    error = state.get('error') or {}
                    message = error.get('message', 'generation failed') if isinstance(error, dict) else str(error)
                    raise EngineError(f'Engine {status}: {message}')
                if status not in ('queued', 'generating'):
                    raise EngineError(f'Unknown engine job status: {status}')
                time.sleep(min(self.poll_interval, max(0, deadline - time.monotonic())))
            raise EngineError(f'Generation timed out after {self.timeout:g} seconds')
        finally:
            if native_id and not terminal:
                try:
                    self.request('POST', '/sdcpp/v1/jobs/' + quote(native_id, safe='') + '/cancel', {})
                except EngineError:
                    pass  # Handler also terminates this process, including unconfirmed submissions.
