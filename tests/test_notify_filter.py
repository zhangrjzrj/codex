import importlib.util
import json
import pathlib
import unittest


SCRIPT_PATH = pathlib.Path(__file__).parents[1] / "codex-notify.py"
SPEC = importlib.util.spec_from_file_location("notify_script", SCRIPT_PATH)
NOTIFY_SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NOTIFY_SCRIPT)


class NotifyFilterTests(unittest.TestCase):
    def test_user_turn_is_not_suppressed(self):
        notification = {
            "type": "agent-turn-complete",
            "input-messages": ["请分析这个崩溃"],
            "last-assistant-message": "根因已经确认。",
        }

        self.assertFalse(
            NOTIFY_SCRIPT.is_internal_task(notification, json.dumps(notification))
        )

    def test_catch_up_task_is_suppressed(self):
        notification = {
            "type": "agent-turn-complete",
            "input-messages": [
                "Write a brief catch-up for a user returning to this Codex task."
            ],
        }

        self.assertTrue(
            NOTIFY_SCRIPT.is_internal_task(notification, json.dumps(notification))
        )

    def test_title_task_is_suppressed(self):
        notification = {
            "type": "agent-turn-complete",
            "input-messages": [
                "Generate a concise, single-line task title of at most 36 characters."
            ],
        }

        self.assertTrue(
            NOTIFY_SCRIPT.is_internal_task(notification, json.dumps(notification))
        )

    def test_malformed_payload_still_suppresses_internal_task(self):
        raw = (
            '{"type":"agent-turn-complete","input-messages":['
            '"Write a brief catch-up for a user returning to this Codex task."],'
            '"last-assistant-message":"broken "quote""}'
        )

        notification = NOTIFY_SCRIPT.parse_notification(raw)

        self.assertTrue(NOTIFY_SCRIPT.is_internal_task(notification, raw))


if __name__ == "__main__":
    unittest.main()
