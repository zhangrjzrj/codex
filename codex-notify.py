#!/usr/bin/env python3
"""
Codex 任务完成通知：用 Python 接 Codex 的 argv JSON，再发 Windows 通知。
当 Codex 在无桌面会话中调用本脚本时，同进程的 toast/MessageBox 不会出现，
因此增加「计划任务」方式：在用户会话中执行 .ps1 弹 BurntToast。
配置: 在 ~/.codex/config.toml 中 notify = ["python", "本脚本的完整路径"]
依赖: pip install win11toast（可选）；计划任务方式需已安装 BurntToast 的 PowerShell。
"""
import json
import re
import sys
import os
import time
import subprocess

# 脚本所在目录，用于日志、消息文件、.ps1 路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "codex-notify.log")
# 备用日志：Codex 可能从别的工作目录调用，便于在固定位置查看
LOG_FILE_ALT = os.path.join(os.environ.get("LOCALAPPDATA", ""), "CodexNotify", "codex-notify.log")
MSG_FILE = os.path.join(SCRIPT_DIR, "codex-notify-msg.txt")
PS1_FILE = os.path.join(SCRIPT_DIR, "codex-notify-toast.ps1")
TASK_NAME = "CodexNotify"


def log(msg: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(LOG_FILE_ALT), exist_ok=True)
        with open(LOG_FILE_ALT, "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass


def _extract_json_string_field(raw: str, field: str):
    m = re.search(r'"' + re.escape(field) + r'"\s*:\s*"((?:\\.|[^"\\])*)"', raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads('"' + m.group(1) + '"')
    except Exception:
        return m.group(1)


def parse_notification(raw: str):
    """Parse Codex notify argv. Fall back to a basic completion notice if JSON is malformed."""
    raw = raw.strip()
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    for a, b in [
        ("\u201c", '"'), ("\u201d", '"'), ("\u2018", "'"), ("\u2019", "'"),
        ("\uff02", '"'), ("\u00ab", '"'), ("\u00bb", '"'),
    ]:
        raw = raw.replace(a, b)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        log(f"json parse failed: {exc}")
    if raw.startswith("{") and "type:agent-turn-complete" in raw and "last-assistant-message:" in raw:
        m = re.search(r"last-assistant-message:(.+)$", raw, re.DOTALL)
        if m:
            msg = m.group(1).strip().rstrip("}").strip()
            return {"type": "agent-turn-complete", "last-assistant-message": msg}
    if "agent-turn-complete" in raw:
        msg = _extract_json_string_field(raw, "last-assistant-message") or "Turn complete."
        return {"type": "agent-turn-complete", "last-assistant-message": msg}
    return None

def show_toast_win11(title: str, message: str) -> bool:
    try:
        from win11toast import toast
        toast(title, message)
        time.sleep(2)
        return True
    except ImportError:
        return False
    except Exception:
        return False


def show_toast_messagebox(title: str, message: str) -> bool:
    try:
        import ctypes
        msg = (message[: 500] + "…") if len(message) > 500 else message
        ctypes.windll.user32.MessageBoxW(None, msg, title, 0x40)
        return True
    except Exception:
        return False


def ensure_task() -> bool:
    """确保计划任务 CodexNotify 存在，用于在用户会话中弹 toast。"""
    r = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME],
        capture_output=True,
        timeout=5,
    )
    if r.returncode == 0:
        return True
    if not os.path.isfile(PS1_FILE):
        return False
    # 创建任务：按需运行，执行 .ps1 并传入消息文件路径
    tr = (
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{PS1_FILE}" -MsgFile "{MSG_FILE}"'
    )
    r = subprocess.run(
        ["schtasks", "/create", "/tn", TASK_NAME, "/tr", tr, "/sc", "once", "/st", "00:00", "/f"],
        capture_output=True,
        timeout=10,
    )
    return r.returncode == 0


def show_toast_via_task(title: str, message: str) -> bool:
    """通过计划任务在用户会话中弹 BurntToast。"""
    try:
        with open(MSG_FILE, "w", encoding="utf-8") as f:
            f.write(message)
    except Exception:
        return False
    if not ensure_task():
        return False
    r = subprocess.run(
        ["schtasks", "/run", "/tn", TASK_NAME],
        capture_output=True,
        timeout=10,
    )
    return r.returncode == 0


def main() -> int:
    from datetime import datetime
    log(f"--- {datetime.now().isoformat()} ---")
    log(f"argv len={len(sys.argv)}")
    if len(sys.argv) < 2:
        log("exit: no argv[1]")
        return 0
    raw = " ".join(sys.argv[1:])
    log(f"argv[1][:300]={repr(raw[:300])}")
    notification = parse_notification(raw)
    if not notification:
        log("exit: parse_notification failed")
        return 0
    message = (notification.get("last-assistant-message") or "Turn complete.")[:200]
    strip_brand = str(os.environ.get("CODEX_NOTIFY_STRIP_BRAND", "1")).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }
    if strip_brand:
        message = re.sub(r"(?i)\bcodex\b", "", message)
    message = re.sub(r"\s+", " ", message).strip(" -:|") or "Turn complete."
    title = (os.environ.get("CODEX_NOTIFY_TITLE") or "任务完成").strip() or "任务完成"
    log(f"message={repr(message[:80])}")

    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass

    if os.environ.get("CODEX_NOTIFY_FORCE_MESSAGEBOX"):
        show_toast_messagebox(title, message)
        log("shown: messagebox (forced)")
        return 0

    # Codex 可能在无桌面会话中调用，此时同进程 toast 不显示；可设 CODEX_NOTIFY_USE_TASK=1 强制走计划任务
    if os.environ.get("CODEX_NOTIFY_USE_TASK"):
        if show_toast_via_task(title, message):
            log("shown: scheduled task (forced)")
            return 0

    if show_toast_win11(title, message):
        log("shown: win11toast")
        return 0
    if show_toast_messagebox(title, message):
        log("shown: messagebox")
        return 0
    if show_toast_via_task(title, message):
        log("shown: scheduled task (BurntToast)")
        return 0
    log("shown: none (all methods failed or skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

