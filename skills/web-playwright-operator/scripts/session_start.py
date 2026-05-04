from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / 'session_state.json'
USER_DATA_DIR = BASE_DIR / 'user-data'


def find_chrome() -> str | None:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--port', type=int, default=9223)
    args = parser.parse_args()

    chrome = find_chrome()
    if not chrome:
        raise SystemExit('Chrome/Edge not found')

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        chrome,
        f'--remote-debugging-port={args.port}',
        f'--user-data-dir={str(USER_DATA_DIR)}',
        '--new-window',
        args.url,
    ]

    proc = subprocess.Popen(cmd)

    state = {
        'pid': proc.pid,
        'port': args.port,
        'user_data_dir': str(USER_DATA_DIR),
        'started_at': int(time.time()),
        'url': args.url,
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"started pid={proc.pid} port={args.port}")
    print(f"state={STATE_PATH}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
