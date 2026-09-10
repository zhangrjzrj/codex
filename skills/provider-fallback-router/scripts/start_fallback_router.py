import os
import subprocess
import sys


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
    subprocess.Popen(
        [sys.executable, router],
        env=environment,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
