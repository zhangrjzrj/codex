import os
import subprocess
import sys
from pathlib import Path


def _debug_enabled(environment: dict[str, str]) -> bool:
    value = environment.get("J_DEBUG", environment.get("J_LOG_MODE", "")).strip().lower()
    return value in {"1", "true", "yes", "on", "debug"}


def _debug_log_path(environment: dict[str, str]) -> Path:
    configured = environment.get("J_DEBUG_LOG", "").strip()
    if configured:
        return Path(configured).expanduser()
    home = Path(environment.get("USERPROFILE") or environment.get("HOME") or ".")
    return home / ".codex" / "logs" / "jfallback-debug.log"


def main() -> int:
    environment = dict(os.environ)
    required = ("J_PRIMARY_BASE", "J_PRIMARY_KEY", "J_SECONDARY_BASE", "J_SECONDARY_KEY")
    missing = [name for name in required if not environment.get(name, "").strip()]
    if missing:
        raise SystemExit("Missing environment variables: " + ", ".join(missing))
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        environment.pop(name, None)
    environment["J_HOST"] = environment.get("J_HOST", "127.0.0.1")
    environment["J_PORT"] = environment.get("J_PORT", "8787")
    router = os.path.join(os.path.dirname(__file__), "fallback_router.py")

    stdout = subprocess.DEVNULL
    stderr = subprocess.DEVNULL
    if _debug_enabled(environment):
        log_path = _debug_log_path(environment)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("a", encoding="utf-8")
        stdout = log_handle
        stderr = log_handle

    subprocess.Popen(
        [sys.executable, router],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
