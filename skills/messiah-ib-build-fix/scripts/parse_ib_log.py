#!/usr/bin/env python3
"""Parse IncrediBuild/MSBuild logs into a ranked, machine-readable report."""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

LOCATION_PATTERN = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+)(?:,(?P<column>\d+))?\):\s*"
    r"(?P<level>fatal error|error|warning)\s*(?P<code>[A-Z]+\d+):\s*(?P<message>.+)$"
)

TARGET_PATTERN = re.compile(
    r"^(?P<file>.+?)\s*:\s*(?P<level>fatal error|error|warning)\s*"
    r"(?P<code>[A-Z]+\d+):\s*(?P<message>.+)$"
)

TOOL_PATTERN = re.compile(
    r"^(?P<tool>LINK|LIB|MSBUILD|NMAKE|cl)\s*:\s*(?P<level>fatal error|error|warning)\s*"
    r"(?P<code>[A-Z]+\d+):\s*(?P<message>.+)$",
    re.IGNORECASE,
)

ANSI_ESCAPE = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "cp936", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def pick_latest_log(log_dir: Path) -> Path:
    if not log_dir.exists():
        raise FileNotFoundError(f"Log directory not found: {log_dir}")

    candidates = sorted(
        log_dir.glob("*.out.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No *.out.log files under: {log_dir}")
    return candidates[0]


def normalize_signature(code: str, message: str) -> str:
    short_message = re.sub(r"\d+", "#", message.strip().lower())
    short_message = re.sub(r"\s+", " ", short_message)
    return f"{code}:{short_message[:140]}"


def parse_issue(line: str, line_no: int):
    clean = ANSI_ESCAPE.sub("", line).strip()
    if not clean:
        return None

    match = LOCATION_PATTERN.match(clean)
    if match:
        item = match.groupdict()
        return {
            "file": item["file"],
            "line": int(item["line"]),
            "column": int(item["column"]) if item.get("column") else None,
            "level": item["level"].lower(),
            "code": item["code"],
            "message": item["message"].strip(),
            "line_no": line_no,
        }

    match = TOOL_PATTERN.match(clean)
    if match:
        item = match.groupdict()
        return {
            "file": item["tool"],
            "line": None,
            "column": None,
            "level": item["level"].lower(),
            "code": item["code"],
            "message": item["message"].strip(),
            "line_no": line_no,
        }

    match = TARGET_PATTERN.match(clean)
    if match:
        item = match.groupdict()
        return {
            "file": item["file"],
            "line": None,
            "column": None,
            "level": item["level"].lower(),
            "code": item["code"],
            "message": item["message"].strip(),
            "line_no": line_no,
        }

    return None


def summarize(issues, top_n):
    errors = [item for item in issues if "error" in item["level"]]
    warnings = [item for item in issues if item["level"] == "warning"]

    code_counter = Counter(item["code"] for item in errors)
    file_counter = Counter(item["file"] for item in errors)
    signature_counter = Counter(
        normalize_signature(item["code"], item["message"]) for item in errors
    )

    return {
        "counts": {
            "errors": len(errors),
            "warnings": len(warnings),
            "issues": len(issues),
        },
        "top_error_codes": [
            {"code": code, "count": count}
            for code, count in code_counter.most_common(top_n)
        ],
        "top_error_files": [
            {"file": file_path, "count": count}
            for file_path, count in file_counter.most_common(top_n)
        ],
        "top_error_signatures": [
            {"signature": signature, "count": count}
            for signature, count in signature_counter.most_common(top_n)
        ],
        "errors": errors,
        "warnings": warnings,
    }


def print_summary(report):
    counts = report["counts"]
    print(f"errors={counts['errors']} warnings={counts['warnings']} issues={counts['issues']}")

    if report["top_error_codes"]:
        print("top_error_codes:")
        for item in report["top_error_codes"]:
            print(f"  {item['code']}: {item['count']}")

    if report["top_error_files"]:
        print("top_error_files:")
        for item in report["top_error_files"]:
            print(f"  {item['file']}: {item['count']}")


def main():
    parser = argparse.ArgumentParser(description="Parse IncrediBuild output logs")
    parser.add_argument("log", nargs="?", help="Path to a .out.log file")
    parser.add_argument(
        "--latest-from",
        dest="latest_from",
        help="Directory that contains .out.log files; parse the latest one",
    )
    parser.add_argument(
        "--json-out",
        dest="json_out",
        help="Output path for parsed JSON report",
    )
    parser.add_argument("--top", type=int, default=10, help="Top N entries for counters")
    parser.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Return exit code 2 when parsed errors are present",
    )
    args = parser.parse_args()

    if args.latest_from:
        log_path = pick_latest_log(Path(args.latest_from))
    elif args.log:
        log_path = Path(args.log)
    else:
        parser.error("provide a log path or --latest-from")

    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    text = read_text(log_path)
    issues = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        issue = parse_issue(line, line_no)
        if issue is not None:
            issues.append(issue)

    report = summarize(issues, max(args.top, 1))
    report["log_file"] = str(log_path)
    report["line_count"] = len(text.splitlines())

    json_out = Path(args.json_out) if args.json_out else Path(str(log_path) + ".parsed.json")
    json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"log_file={log_path}")
    print(f"json_out={json_out}")
    print_summary(report)

    if args.fail_on_errors and report["counts"]["errors"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[parse_ib_log] {exc}", file=sys.stderr)
        raise

