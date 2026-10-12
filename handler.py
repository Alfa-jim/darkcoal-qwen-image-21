"""RunPod queue handler. Importing this module does not start CUDA or the SDK."""

import atexit
import signal
import threading

from worker.engine import EngineError
from worker.request import build_payload
from worker.runtime import Supervisor

_supervisor = None
_job_lock = threading.Lock()


def handler(job):
    global _supervisor
    try:
        if not isinstance(job, dict):
            raise ValueError('job must be an object')
        payload = build_payload(job.get('input'))
    except ValueError as exc:
        return {'error': str(exc)}
    with _job_lock:
        if _supervisor is None:
            _supervisor = Supervisor()
        try:
            _supervisor.ensure_started()
            return _supervisor.client.generate(payload, job.get('id', 'image'))
        except (EngineError, RuntimeError, OSError) as exc:
            # Also kills jobs whose POST response was lost before we received an id.
            _supervisor.stop()
            return {'error': str(exc)}


def main():
    global _supervisor
    _supervisor = Supervisor()
    atexit.register(_supervisor.stop)

    def terminate(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        # Never register a healthy worker before CUDA/model initialization succeeds.
        _supervisor.ensure_started()
        import runpod
        runpod.serverless.start({'handler': handler})
    finally:
        _supervisor.stop()


if __name__ == '__main__':
    main()
