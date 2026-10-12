"""Supervise a single persistent, private CUDA inference server."""

import os
from pathlib import Path
import subprocess
import time

from worker.engine import EngineClient, EngineError
from worker.models import validate_models
from worker.request import SIGMAS


def build_command(paths, port=1234):
    return [os.environ.get('SD_SERVER_BIN', '/usr/local/bin/sd-server'),
            '--diffusion-model', str(paths['denoiser']),
            '--llm', str(paths['encoder']), '--llm_vision', str(paths['vision']),
            '--vae', str(paths['vae']), '--listen-ip', '127.0.0.1',
            '--listen-port', str(port), '--diffusion-fa', '--offload-to-cpu',
            '--steps', '8', '--cfg-scale', '1.0', '--sampling-method', 'euler',
            '--sigmas', ','.join(str(number) for number in SIGMAS),
            '--rng', 'cpu']


class Supervisor:
    def __init__(self):
        self.process = None
        self.volume_root = Path(os.environ.get('MODEL_VOLUME_ROOT', '/runpod-volume'))
        self.start_timeout = float(os.environ.get('ENGINE_START_TIMEOUT', '300'))
        self.port = int(os.environ.get('ENGINE_PORT', '1234'))
        job_timeout = float(os.environ.get('JOB_TIMEOUT_SECONDS', '900'))
        if self.start_timeout <= 0 or job_timeout <= 0 or not 1 <= self.port <= 65535:
            raise ValueError('Engine timeout values must be positive and ENGINE_PORT must be 1–65535')
        self.client = EngineClient(f'http://127.0.0.1:{self.port}', timeout=job_timeout)

    def ensure_started(self):
        if self.process is not None and self.process.poll() is None:
            return
        if not os.path.ismount(self.volume_root):
            raise RuntimeError(f'Network volume is not mounted at {self.volume_root}. '
                               'Attach the prepared volume to this endpoint.')
        paths = validate_models(self.volume_root,
                                verify_hashes=os.environ.get('VERIFY_MODEL_HASHES', '0') == '1')
        print('Starting pinned Qwen Image 2.1 Q4 CUDA engine', flush=True)
        self.process = subprocess.Popen(build_command(paths, self.port))
        deadline = time.monotonic() + self.start_timeout
        try:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(f'Inference engine exited with code {self.process.returncode}; '
                                       'check preceding CUDA/model logs')
                try:
                    capabilities = self.client.capabilities()
                except EngineError:
                    time.sleep(1)
                    continue
                if ('img_gen' not in capabilities.get('supported_modes', []) or
                        not capabilities.get('features_by_mode', {}).get('img_gen', {}).get('ref_images')):
                    raise RuntimeError('Engine does not advertise image generation and reference support')
                print('Qwen engine ready; network-volume assets loaded', flush=True)
                return
            raise RuntimeError(f'Engine startup timed out after {self.start_timeout:g} seconds')
        except BaseException:
            self.stop()
            raise

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=10)
            self.process = None
