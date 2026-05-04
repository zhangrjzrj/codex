from __future__ import annotations

import json
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / 'session_state.json'


def main() -> int:
    if not STATE_PATH.exists():
        print('no session')
        return 0

    state = json.loads(STATE_PATH.read_text(encoding='utf-8'))
    pid = state.get('pid')

    if pid:
        subprocess.run(['taskkill', '/PID', str(pid), '/F'], check=False)

    STATE_PATH.unlink(missing_ok=True)
    print('stopped')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
