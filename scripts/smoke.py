#!/usr/bin/env python3
"""No-model/no-GPU image smoke test, run during Docker build and CI."""

from pathlib import Path
import os
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import handler
import runpod
from worker.models import load_manifest
from worker.request import build_payload
from worker.runtime import build_command


def main():
    assert callable(handler.handler)
    assert len(load_manifest()['assets']) == 4
    assert build_payload({'prompt': 'smoke'})['sample_params']['sample_steps'] == 8
    smoke_env = dict(os.environ)
    # --help does not initialize CUDA. Production startup receives the actual
    # NVIDIA driver library; this per-subprocess setting never escapes the test.
    smoke_env['LD_LIBRARY_PATH'] = '/opt/cuda-stubs:' + smoke_env.get('LD_LIBRARY_PATH', '')
    help_text = subprocess.check_output(['/usr/local/bin/sd-server', '--help'],
                                        text=True, stderr=subprocess.STDOUT, env=smoke_env)
    paths = {role: Path('/not-loaded/' + role) for role in ('denoiser', 'encoder', 'vision', 'vae')}
    command = build_command(paths)
    for flag in command[1:]:
        if flag.startswith('--'):
            assert flag in help_text, f'Missing pinned engine option: {flag}'
    assert '--sigmas' in help_text
    print('CPU smoke passed: worker imports, model lock, Turbo request and engine flags')


if __name__ == '__main__':
    main()
