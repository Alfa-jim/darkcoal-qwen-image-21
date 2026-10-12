import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import handler
from worker.engine import EngineError
from worker.runtime import Supervisor, build_command


class RuntimeTests(unittest.TestCase):
    def test_server_command_loads_all_assets_and_turbo_defaults(self):
        paths = {key: Path('/volume/' + key) for key in ('denoiser', 'encoder', 'vision', 'vae')}
        command = build_command(paths, port=1234)
        for flag, role in (('--diffusion-model', 'denoiser'), ('--llm', 'encoder'),
                           ('--llm_vision', 'vision'), ('--vae', 'vae')):
            self.assertEqual(command[command.index(flag) + 1], str(paths[role]))
        self.assertIn('--diffusion-fa', command)
        self.assertEqual(command[command.index('--listen-ip') + 1], '127.0.0.1')
        self.assertEqual(command[command.index('--steps') + 1], '8')
        self.assertEqual(len(command[command.index('--sigmas') + 1].split(',')), 9)

    def test_start_refuses_unmounted_volume(self):
        supervisor = Supervisor()
        with patch('os.path.ismount', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'volume'):
                supervisor.ensure_started()

    def test_startup_process_failure_terminates_without_worker_readiness(self):
        supervisor = Supervisor()
        process = Mock()
        process.poll.return_value = 1
        with patch('os.path.ismount', return_value=True), \
                patch('worker.runtime.validate_models', return_value={}), \
                patch('worker.runtime.build_command', return_value=['sd-server']), \
                patch('worker.runtime.subprocess.Popen', return_value=process):
            with self.assertRaisesRegex(RuntimeError, 'exited'):
                supervisor.ensure_started()

    def test_handler_validation_does_not_start_engine(self):
        runtime = Mock()
        with patch.object(handler, '_supervisor', runtime):
            result = handler.handler({'id': 'x', 'input': {'prompt': ''}})
        self.assertIn('error', result)
        runtime.ensure_started.assert_not_called()

    def test_handler_recycles_engine_on_failure_and_recovers_next_job(self):
        runtime = Mock()
        runtime.client.generate.side_effect = [EngineError('CUDA out of memory'),
                                               {'images': [{'type': 'base64', 'data': 'ok'}]}]
        with patch.object(handler, '_supervisor', runtime):
            first = handler.handler({'id': 'x', 'input': {'prompt': 'cat'}})
            second = handler.handler({'id': 'y', 'input': {'prompt': 'cat'}})
        self.assertIn('out of memory', first['error'])
        self.assertTrue(second['images'])
        runtime.stop.assert_called_once()
