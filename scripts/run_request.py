#!/usr/bin/env python3
"""Submit /run, poll /status, and save PNG outputs without exposing the API key."""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import quote
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--input', type=Path, default=Path('test_input.json'))
    parser.add_argument('--output-dir', type=Path, default=Path('.validation'))
    parser.add_argument('--timeout', type=int, default=1200)
    args = parser.parse_args()
    key = os.environ.get('RUNPOD_API_KEY')
    if not key:
        parser.error('Set RUNPOD_API_KEY in your environment')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.endpoint):
        parser.error('endpoint must be a RunPod endpoint ID, not a URL')
    base = 'https://api.runpod.ai/v2/' + args.endpoint

    def call(path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(base + path, data=body,
                          headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=60) as response:
            return json.load(response)

    job = call('/run', json.loads(args.input.read_text(encoding='utf-8')))
    job_id = job['id']
    print(f'RunPod job: {job_id}', flush=True)
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        state = call('/status/' + quote(job_id, safe=''))
        if state['status'] == 'COMPLETED':
            output = state.get('output') or {}
            if output.get('error'):
                raise SystemExit('Worker failed: ' + str(output['error']))
            images = output.get('images') or []
            if not images:
                raise SystemExit('Completed job returned no images')
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for index, image in enumerate(images):
                if image.get('type') != 'base64':
                    raise SystemExit('Unexpected output format')
                target = args.output_dir / f'{job_id}_{index}.png'
                target.write_bytes(base64.b64decode(image['data'], validate=True))
                print(target)
            metadata = {field: state.get(field) for field in ('id', 'status', 'delayTime', 'executionTime')}
            (args.output_dir / f'{job_id}.json').write_text(json.dumps(metadata, indent=2))
            print(json.dumps(metadata))
            return
        if state['status'] in ('FAILED', 'CANCELLED', 'TIMED_OUT'):
            raise SystemExit(json.dumps({'status': state['status'], 'error': state.get('error')}))
        time.sleep(2)
    call('/cancel/' + quote(job_id, safe=''), {})
    raise SystemExit('Client wait timed out; RunPod cancellation requested')


if __name__ == '__main__':
    main()
