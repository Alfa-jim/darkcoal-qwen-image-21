#!/usr/bin/env python3
"""Generate a pasteable offline bootstrap from the installer and model lock."""

import argparse
import base64
import hashlib
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def make_command():
    installer = (ROOT / 'scripts/download_models.py').read_bytes()
    lock = (ROOT / 'model-lock.json').read_bytes()
    script_b64 = '\n'.join(textwrap.wrap(base64.b64encode(installer).decode(), 100))
    lock_b64 = '\n'.join(textwrap.wrap(base64.b64encode(lock).decode(), 100))
    return f'''#!/usr/bin/env bash
# Paste this entire file into a CPU Pod terminal with your NETWORK VOLUME attached.
# Default mount: /workspace. For another mount, first: export MODEL_VOLUME_ROOT=/your/mount
# Generated; regenerate with: python scripts/make_download_command.py
set -euo pipefail
if ! command -v python3 >/dev/null; then
  apt-get update
  apt-get install -y python3
fi
python3 - <<'QWEN21_BOOTSTRAP'
import base64, hashlib, json, os, pathlib, sys
if sys.version_info < (3, 11):
    raise SystemExit('Python 3.11+ required. Use a current Ubuntu 24.04 CPU Pod template.')
volume = pathlib.Path(os.environ.get('MODEL_VOLUME_ROOT', '/workspace')).resolve()
if not volume.is_dir() or not os.path.ismount(volume):
    raise SystemExit(f'ERROR: {{volume}} is not an attached network-volume mount. Attach the volume when creating the Pod.')
installer = base64.b64decode(''' + '"""' + script_b64 + '"""' + f''')
manifest = base64.b64decode(''' + '"""' + lock_b64 + '"""' + f''')
assert hashlib.sha256(installer).hexdigest() == '{hashlib.sha256(installer).hexdigest()}'
assert hashlib.sha256(manifest).hexdigest() == '{hashlib.sha256(lock).hexdigest()}'
cache = volume / 'models/qwen-image-21/.cache'
cache.mkdir(parents=True, exist_ok=True)
installer_path = cache / 'download_models.py'
manifest_path = cache / 'model-lock.json'
installer_path.write_bytes(installer)
manifest_path.write_bytes(manifest)
namespace = {{'__name__': 'qwen21_installer', '__file__': str(installer_path)}}
exec(compile(installer, str(installer_path), 'exec'), namespace)
namespace['prepare'](volume, json.loads(manifest))
QWEN21_BOOTSTRAP
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    target = ROOT / 'DOWNLOAD_ON_CPU_POD.sh'
    command = make_command()
    if args.check:
        if not target.exists() or target.read_text() != command:
            raise SystemExit('Bootstrap differs from installer/model lock. Regenerate it.')
        print('Pasteable CPU bootstrap matches installer and pinned model lock')
    else:
        target.write_text(command, encoding='utf-8', newline='\n')
        print(target)


if __name__ == '__main__':
    main()
