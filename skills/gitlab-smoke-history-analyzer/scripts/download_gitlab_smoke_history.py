#!/usr/bin/env python3
"""Download read-only GitLab pipeline metadata, job traces, and artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def api_get(base: str, endpoint: str, token: str) -> tuple[bytes, dict[str, str]]:
    request = urllib.request.Request(
        base.rstrip("/") + endpoint,
        headers={"PRIVATE-TOKEN": token},
    )
    with urllib.request.urlopen(request) as response:
        return response.read(), dict(response.headers.items())


def json_get(base: str, endpoint: str, token: str) -> Any:
    payload, _ = api_get(base, endpoint, token)
    return json.loads(payload.decode("utf-8"))


def write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", required=True, help="GitLab API v4 base URL")
    parser.add_argument("--project", required=True, help="Numeric ID or namespace/project path")
    parser.add_argument("--ref", required=True, help="Branch ref to inspect")
    parser.add_argument("--output", type=Path, required=True, help="Ignored evidence directory")
    parser.add_argument("--limit", type=int, default=20, help="Maximum pipelines to retrieve")
    parser.add_argument("--job-regex", default="smoke", help="Case-insensitive regular expression selecting jobs")
    args = parser.parse_args()

    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        parser.error("GITLAB_TOKEN must be set; the token is never printed")
    if args.limit < 1:
        parser.error("--limit must be positive")
    try:
        selector = re.compile(args.job_regex, re.IGNORECASE)
    except re.error as error:
        parser.error(f"invalid --job-regex: {error}")

    project = urllib.parse.quote(args.project, safe="")
    query = urllib.parse.urlencode({"ref": args.ref, "per_page": args.limit, "order_by": "id", "sort": "desc"})
    pipelines = json_get(args.api_base, f"/projects/{project}/pipelines?{query}", token)
    if not isinstance(pipelines, list):
        raise RuntimeError("pipeline response is not a list")

    manifest: list[dict[str, Any]] = []
    for pipeline in pipelines:
        pipeline_id = pipeline["id"]
        jobs = json_get(args.api_base, f"/projects/{project}/pipelines/{pipeline_id}/jobs?per_page=100", token)
        for job in jobs:
            if not selector.search(str(job.get("name", ""))):
                continue
            job_id = job["id"]
            entry = {
                "pipeline_id": pipeline_id,
                "pipeline_sha": pipeline.get("sha"),
                "pipeline_status": pipeline.get("status"),
                "job_id": job_id,
                "job_name": job.get("name"),
                "job_status": job.get("status"),
                "job_failure_reason": job.get("failure_reason"),
                "runner": (job.get("runner") or {}).get("description"),
                "retrieved_at_epoch": int(time.time()),
            }
            job_root = args.output / f"pipeline-{pipeline_id}" / f"job-{job_id}"
            write_bytes(job_root / "metadata.json", json.dumps(entry, indent=2, ensure_ascii=True).encode("utf-8") + b"\n")
            try:
                artifact, _ = api_get(args.api_base, f"/projects/{project}/jobs/{job_id}/artifacts", token)
                write_bytes(job_root / "artifacts.zip", artifact)
                entry["artifact_downloaded"] = True
            except Exception as error:
                entry["artifact_downloaded"] = False
                entry["artifact_error"] = str(error)
            try:
                trace, _ = api_get(args.api_base, f"/projects/{project}/jobs/{job_id}/trace", token)
                write_bytes(job_root / "job-trace.log", trace)
                entry["trace_downloaded"] = True
            except Exception as error:
                entry["trace_downloaded"] = False
                entry["trace_error"] = str(error)
            write_bytes(job_root / "metadata.json", json.dumps(entry, indent=2, ensure_ascii=True).encode("utf-8") + b"\n")
            manifest.append(entry)

    write_bytes(args.output / "manifest.json", json.dumps({"pipelines": len(pipelines), "jobs": manifest}, indent=2, ensure_ascii=True).encode("utf-8") + b"\n")
    print(f"Downloaded metadata for {len(manifest)} matching jobs into {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
