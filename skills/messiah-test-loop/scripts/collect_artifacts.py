#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DUMP_PATTERNS = ("*.dmp", "*.mdmp")


@dataclass
class CollectResult:
    copied_logs: list[str]
    copied_dumps: list[str]
    dump_count: int


def list_dump_files(repo_root: Path) -> list[Path]:
    candidates = [
        repo_root / "Messiah" / "LocalData",
        repo_root / "Messiah" / "Engine" / "SDKTools" / "Joker" / "stackdump" / "dumps",
        repo_root / "cooked_client" / "Client" / "LocalData",
        repo_root / "cooked_client" / "Client" / "Engine" / "SDKTools" / "Joker" / "stackdump" / "dumps",
    ]
    out: list[Path] = []
    for base in candidates:
        if not base.exists():
            continue
        for pattern in DUMP_PATTERNS:
            out.extend(base.rglob(pattern))
    unique = sorted({p.resolve() for p in out}, key=lambda p: p.stat().st_mtime, reverse=True)
    return unique


def copy_recent_logs(log_dir: Path, dest_dir: Path, since_ts: float, limit: int = 20) -> list[Path]:
    if not log_dir.exists():
        return []
    dest_dir.mkdir(parents=True, exist_ok=True)
    logs = sorted(log_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    copied: list[Path] = []
    for log in logs:
        if len(copied) >= limit:
            break
        if log.stat().st_mtime < since_ts:
            continue
        dst = dest_dir / log.name
        shutil.copy2(log, dst)
        copied.append(dst)
    return copied


def copy_dump_files(dumps: Iterable[Path], dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for src in dumps:
        if not src.exists():
            continue
        dst = dest_dir / src.name
        suffix = 1
        while dst.exists():
            dst = dest_dir / f"{src.stem}_{suffix}{src.suffix}"
            suffix += 1
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def collect(
    repo_root: Path,
    log_dir: Path,
    out_dir: Path,
    since_ts: float,
    known_dumps: set[str] | None = None,
) -> CollectResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    copied_logs = copy_recent_logs(log_dir, out_dir / "logs", since_ts)

    known_dumps = known_dumps or set()
    all_dumps = list_dump_files(repo_root)
    new_dumps = [p for p in all_dumps if str(p) not in known_dumps]
    copied_dumps = copy_dump_files(new_dumps, out_dir / "dumps")

    return CollectResult(
        copied_logs=[str(p) for p in copied_logs],
        copied_dumps=[str(p) for p in copied_dumps],
        dump_count=len(new_dumps),
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Collect recent Messiah logs and dumps.")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--since", type=float, default=time.time() - 600)
    parser.add_argument("--known-dumps-file", type=Path, default=None)
    args = parser.parse_args()

    known: set[str] = set()
    if args.known_dumps_file and args.known_dumps_file.exists():
        try:
            known = set(json.loads(args.known_dumps_file.read_text(encoding="utf-8")))
        except Exception:
            known = set()

    result = collect(
        repo_root=args.repo_root,
        log_dir=args.log_dir,
        out_dir=args.out_dir,
        since_ts=args.since,
        known_dumps=known,
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
