#!/usr/bin/env python3
"""Summarize extracted GitLab smoke artifacts without contacting GitLab."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


RESULT_NAMES = ("nbs_six_parallel_playback_result.json", "result.json")


@dataclass
class EvidenceRecord:
    source: str
    commit_sha: str | None
    platform: str | None
    status: str
    stage: str
    stream_count: int | None
    advanced_streams: int | None
    success: bool | None
    details: list[str]


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def find_file(root: Path, name: str) -> Path | None:
    matches = sorted(root.rglob(name))
    return matches[0] if matches else None


def find_metadata(root: Path) -> dict[str, Any]:
    for parent in (root, *root.parents):
        metadata = read_json(parent / "metadata.json")
        if metadata:
            return metadata
    return {}


def contains(path: Path | None, marker: str) -> bool:
    if path is None:
        return False
    try:
        return marker in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def classify(root: Path) -> EvidenceRecord:
    smoke_result = find_file(root, RESULT_NAMES[0])
    runner_result = find_file(root, RESULT_NAMES[1])
    result = read_json(smoke_result) if smoke_result else None
    runner = read_json(runner_result) if runner_result else None
    metadata = find_metadata(root)
    platform = (runner or {}).get("platform")
    commit_sha = (runner or {}).get("source_commit_sha") or metadata.get("pipeline_sha")
    details: list[str] = []
    stream_count = None
    advanced_streams = None
    success = None

    cmake_log = find_file(root, "cmake-configure.log")
    xcode_log = find_file(root, "xcodebuild.log")
    gradle_log = find_file(root, "gradle-build.log")
    install_log = find_file(root, "install.log")
    launch_log = find_file(root, "launch.log")

    if result:
        success = result.get("success") if isinstance(result.get("success"), bool) else None
        stream_count = result.get("stream_count") if isinstance(result.get("stream_count"), int) else None
        streams = result.get("stream_results")
        if isinstance(streams, list):
            advanced_streams = sum(item.get("advanced") is True for item in streams if isinstance(item, dict))
        if success is True:
            return EvidenceRecord(str(root), commit_sha, platform, "passed", "passed", stream_count, advanced_streams, success, details)
        stalled = []
        if isinstance(streams, list):
            stalled = [str(item.get("path")) for item in streams if isinstance(item, dict) and item.get("advanced") is not True]
        if stalled:
            details.append("stalled streams: " + ", ".join(stalled))
        if result.get("errors"):
            details.append("errors: " + json.dumps(result["errors"], ensure_ascii=True))
        return EvidenceRecord(str(root), commit_sha, platform, "failed", "playback", stream_count, advanced_streams, success, details)

    if contains(cmake_log, "CMake Error") or contains(cmake_log, "Could not find"):
        return EvidenceRecord(str(root), commit_sha, platform, "failed", "configure", stream_count, advanced_streams, success, details)
    if contains(xcode_log, "** BUILD FAILED **") or contains(gradle_log, "BUILD FAILED"):
        return EvidenceRecord(str(root), commit_sha, platform, "failed", "build", stream_count, advanced_streams, success, details)
    if install_log and not contains(install_log, "Installed"):
        return EvidenceRecord(str(root), commit_sha, platform, "failed", "install", stream_count, advanced_streams, success, details)
    if launch_log and (contains(launch_log, "error") or contains(launch_log, "failed")):
        return EvidenceRecord(str(root), commit_sha, platform, "failed", "launch", stream_count, advanced_streams, success, details)
    if contains(xcode_log, "** BUILD SUCCEEDED **") or contains(gradle_log, "BUILD SUCCESSFUL"):
        return EvidenceRecord(str(root), commit_sha, platform, "passed", "passed", stream_count, advanced_streams, success, details)
    return EvidenceRecord(str(root), commit_sha, platform, "unknown", "unknown", stream_count, advanced_streams, success, details)


def extract_archives(input_root: Path, staging: Path) -> list[Path]:
    roots = [input_root]
    for archive in input_root.rglob("*.zip"):
        target = staging / archive.stem
        if not target.exists():
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.infolist():
                    destination = (target / member.filename).resolve()
                    if target.resolve() not in destination.parents and destination != target.resolve():
                        raise ValueError(f"archive member escapes evidence directory: {member.filename}")
                bundle.extractall(target)
        roots.append(target)
    return roots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Evidence root containing extracted artifacts or zip archives")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON report")
    args = parser.parse_args()

    if not args.input.is_dir():
        parser.error("--input must be an existing directory")
    staging = args.output.parent / ".extracted-artifacts"
    roots = extract_archives(args.input, staging)
    candidates = [root for root in roots if any(find_file(root, name) for name in RESULT_NAMES) or find_file(root, "xcodebuild.log") or find_file(root, "gradle-build.log")]
    records = [asdict(classify(root)) for root in candidates]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"records": records}, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"records": records}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
