import json
import time
import traceback


class AutoLoopOperator:
    BLOCKER_UI_NAMES = (
        "UITraceNotice",
        "UILoginGameQualityStatement",
        "UILoginProtocolTips",
        "UILoginLoadSecondTip",
        "UILoginSureSecondTipsMain",
        "UILoginQueue",
        "UINotice",
        "UISailingMapLoading",
    )

    def __init__(self):
        self.nbs_demo_path = r"E:/messiah_h74/Messiah/NBSDemo.py"
        self._scenario_state = None
        self._nbs_loaded_path = None
        self._nbs_script_env = None
        self._nbs_play_args = {
            "montid": None,
            "nbs": None,
            "start": None,
            "end": None,
            "use_audio_sync": None,
        }

    def _emit(self, payload):
        print("AUTO_JSON::" + json.dumps(payload, ensure_ascii=False))
        print("AUTO_END")

    def ping(self):
        self._emit({"ok": True, "action": "ping"})

    def set_nbs_demo_path(self, path):
        self.nbs_demo_path = path
        self._emit(
            {
                "ok": True,
                "action": "set_nbs_demo_path",
                "path": path,
                "reloaded_on_next_start": bool(self._nbs_loaded_path != path),
            }
        )

    def set_nbs_play_args(self, montid=None, nbs=None, start=None, end=None, use_audio_sync=None):
        try:
            self._nbs_play_args = {
                "montid": None if montid in ("", None) else str(montid),
                "nbs": None if nbs in ("", None) else str(nbs),
                "start": None if start in ("", None) else int(start),
                "end": None if end in ("", None) else int(end),
                "use_audio_sync": use_audio_sync,
            }
            self._emit(
                {
                    "ok": True,
                    "action": "set_nbs_play_args",
                    **self._nbs_play_args,
                }
            )
        except Exception as exc:
            self._emit(
                {
                    "ok": False,
                    "action": "set_nbs_play_args",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    @classmethod
    def _dismiss_login_blockers_internal(cls):
        import game_globals as gg

        found = []
        dismissed = []
        errors = {}
        ui_mgr = getattr(gg, "g_ui_mgr", None)
        if ui_mgr is None:
            return {
                "found_count": 0,
                "dismissed_count": 0,
                "found": found,
                "dismissed": dismissed,
                "errors": errors,
            }

        for name in cls.BLOCKER_UI_NAMES:
            try:
                ui = ui_mgr.get_ui(name)
            except Exception as exc:
                errors[name] = repr(exc)
                continue
            if not ui:
                continue
            found.append(name)
            try:
                ui_mgr.hide_popup(name)
                dismissed.append(name)
            except Exception as exc:
                errors[name] = repr(exc)

        return {
            "found_count": len(found),
            "dismissed_count": len(dismissed),
            "found": found,
            "dismissed": dismissed,
            "errors": errors,
        }

    def dismiss_login_blockers(self):
        try:
            stats = self._dismiss_login_blockers_internal()
            self._emit(
                {
                    "ok": True,
                    "action": "dismiss_login_blockers",
                    "found_count": stats["found_count"],
                    "dismissed_count": stats["dismissed_count"],
                    "found": stats["found"],
                    "dismissed": stats["dismissed"],
                    "errors": stats["errors"],
                }
            )
        except Exception as exc:
            self._emit(
                {
                    "ok": False,
                    "action": "dismiss_login_blockers",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    @staticmethod
    def _get_login_uis():
        import game_globals as gg

        ui_login = None
        ui_login_main = None
        if getattr(gg, "g_ui_mgr", None):
            ui_login = gg.g_ui_mgr.get_ui("UILogin")
            ui_login_main = gg.g_ui_mgr.get_ui("UILoginMain")
        return ui_login, ui_login_main

    @staticmethod
    def _inspect_login_state():
        import game_globals as gg

        space_no = getattr(getattr(gg, "space", None), "spaceno", None)
        scene_ok = space_no not in (None, -1, "1", 1)
        ui_login, ui_login_main = AutoLoopOperator._get_login_uis()
        loading_type = -1
        controlled = False
        if getattr(gg, "g_ui_mgr", None):
            ui_loading_mgr = getattr(gg.g_ui_mgr, "ui_loading_mgr", None)
            if ui_loading_mgr is not None:
                loading_type = getattr(ui_loading_mgr, "showing_ui_type", -1)
        if getattr(gg, "soul_avatar", None):
            controlled = bool(gg.soul_avatar.get_controlled_entity())
        ready = bool(scene_ok and not ui_login and not ui_login_main and loading_type == -1 and controlled)
        return {
            "ready": ready,
            "space_no": space_no,
            "loading_type": loading_type,
            "controlled": controlled,
            "ui_login": bool(ui_login),
            "ui_login_main": bool(ui_login_main),
        }

    def wait_login_ui_ready(self, timeout_sec=10.0, poll_interval_sec=0.2):
        try:
            timeout_sec = float(timeout_sec)
            poll_interval_sec = max(0.05, float(poll_interval_sec))
            deadline = time.time() + max(0.1, timeout_sec)
            last_state = {"ui_login": False, "ui_login_main": False}
            while time.time() < deadline:
                state = self._inspect_login_state()
                last_state = state
                if state.get("ui_login") or state.get("ui_login_main"):
                    ui_type = "UILogin" if state.get("ui_login") else "UILoginMain"
                    self._emit(
                        {
                            "ok": True,
                            "action": "wait_login_ui_ready",
                            "ready": True,
                            "ui_type": ui_type,
                            "timeout_sec": timeout_sec,
                        }
                    )
                    return
                time.sleep(poll_interval_sec)

            self._emit(
                {
                    "ok": True,
                    "action": "wait_login_ui_ready",
                    "ready": False,
                    "ui_type": "",
                    "timeout_sec": timeout_sec,
                    "last_ui_login": bool(last_state.get("ui_login")),
                    "last_ui_login_main": bool(last_state.get("ui_login_main")),
                }
            )
        except Exception as exc:
            self._emit(
                {
                    "ok": False,
                    "action": "wait_login_ui_ready",
                    "ready": False,
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    def click_start_game(self):
        try:
            ui_login, ui_login_main = self._get_login_uis()

            if ui_login:
                ui_login.login_by_other_ui()
                self._emit(
                    {
                        "ok": True,
                        "action": "click_start_game",
                        "clicked": True,
                        "ui_type": "UILogin",
                    }
                )
                return
            if ui_login_main:
                ui_login_main.login_by_other_ui()
                self._emit(
                    {
                        "ok": True,
                        "action": "click_start_game",
                        "clicked": True,
                        "ui_type": "UILoginMain",
                    }
                )
                return

            self._emit(
                {
                    "ok": False,
                    "action": "click_start_game",
                    "clicked": False,
                    "error": "login ui not found",
                }
            )
        except Exception as exc:
            self._emit(
                {
                    "ok": False,
                    "action": "click_start_game",
                    "clicked": False,
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    def click_start_game_with_retry(self, max_attempts=5, interval_sec=0.5, wait_ready_timeout_sec=1.0):
        try:
            max_attempts = max(1, int(max_attempts))
            interval_sec = max(0.0, float(interval_sec))
            wait_ready_timeout_sec = max(0.0, float(wait_ready_timeout_sec))

            attempts_used = 0
            click_count = 0
            last_ui_type = ""
            stop_reason = "attempts_exhausted"
            blockers_found_total = 0
            blockers_dismissed_total = 0

            for i in range(max_attempts):
                attempts_used = i + 1
                blocker_stats = self._dismiss_login_blockers_internal()
                blockers_found_total += int(blocker_stats.get("found_count", 0))
                blockers_dismissed_total += int(blocker_stats.get("dismissed_count", 0))

                ui_login, ui_login_main = self._get_login_uis()
                if ui_login:
                    ui_login.login_by_other_ui()
                    click_count += 1
                    last_ui_type = "UILogin"
                elif ui_login_main:
                    ui_login_main.login_by_other_ui()
                    click_count += 1
                    last_ui_type = "UILoginMain"
                else:
                    stop_reason = "ui_not_present"
                    break

                if interval_sec > 0:
                    time.sleep(interval_sec)

                check_deadline = time.time() + wait_ready_timeout_sec
                while True:
                    state = self._inspect_login_state()
                    if state.get("ready"):
                        stop_reason = "login_ready"
                        self._emit(
                            {
                                "ok": True,
                                "action": "click_start_game_with_retry",
                                "success": True,
                                "clicked": click_count > 0,
                                "attempts_used": attempts_used,
                                "max_attempts": max_attempts,
                                "click_count": click_count,
                                "reason": stop_reason,
                                "last_ui_type": last_ui_type,
                                "blockers_found_count": blockers_found_total,
                                "blockers_dismissed_count": blockers_dismissed_total,
                            }
                        )
                        return
                    if not state.get("ui_login") and not state.get("ui_login_main"):
                        stop_reason = "ui_gone"
                        self._emit(
                            {
                                "ok": True,
                                "action": "click_start_game_with_retry",
                                "success": True,
                                "clicked": click_count > 0,
                                "attempts_used": attempts_used,
                                "max_attempts": max_attempts,
                                "click_count": click_count,
                                "reason": stop_reason,
                                "last_ui_type": last_ui_type,
                                "blockers_found_count": blockers_found_total,
                                "blockers_dismissed_count": blockers_dismissed_total,
                            }
                        )
                        return
                    if time.time() >= check_deadline:
                        break
                    time.sleep(0.1)

            self._emit(
                {
                    "ok": True,
                    "action": "click_start_game_with_retry",
                    "success": False,
                    "clicked": click_count > 0,
                    "attempts_used": attempts_used,
                    "max_attempts": max_attempts,
                    "click_count": click_count,
                    "reason": stop_reason,
                    "last_ui_type": last_ui_type,
                    "blockers_found_count": blockers_found_total,
                    "blockers_dismissed_count": blockers_dismissed_total,
                }
            )
        except Exception as exc:
            self._emit(
                {
                    "ok": False,
                    "action": "click_start_game_with_retry",
                    "success": False,
                    "clicked": False,
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    def fallback_do_gm_login(self):
        try:
            ui_login, _ = self._get_login_uis()
            if not ui_login:
                self._emit(
                    {
                        "ok": True,
                        "action": "fallback_do_gm_login",
                        "success": False,
                        "reason": "uilogin_not_found",
                    }
                )
                return
            ui_login.do_gm_login()
            self._emit(
                {
                    "ok": True,
                    "action": "fallback_do_gm_login",
                    "success": True,
                    "reason": "do_gm_login_called",
                }
            )
        except Exception as exc:
            self._emit(
                {
                    "ok": False,
                    "action": "fallback_do_gm_login",
                    "success": False,
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    def dismiss_trace_notice(self):
        try:
            import game_globals as gg

            ui_mgr = getattr(gg, "g_ui_mgr", None)
            if ui_mgr is None:
                self._emit(
                    {
                        "ok": True,
                        "action": "dismiss_trace_notice",
                        "found": False,
                        "dismissed": False,
                        "reason": "ui_mgr_missing",
                    }
                )
                return

            ui = ui_mgr.get_ui("UITraceNotice")
            found = bool(ui)
            dismissed = False
            if found:
                ui_mgr.hide_popup("UITraceNotice")
                dismissed = True

            self._emit(
                {
                    "ok": True,
                    "action": "dismiss_trace_notice",
                    "found": found,
                    "dismissed": dismissed,
                    "reason": "dismissed" if dismissed else "not_found",
                }
            )
        except Exception as exc:
            self._emit(
                {
                    "ok": False,
                    "action": "dismiss_trace_notice",
                    "found": False,
                    "dismissed": False,
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    def set_login_account(self, account):
        try:
            account = str(account)
            ui_login, ui_login_main = self._get_login_uis()
            if ui_login:
                ui_type = "UILogin"
                ui = ui_login
            elif ui_login_main:
                ui_type = "UILoginMain"
                ui = ui_login_main
            else:
                self._emit(
                    {
                        "ok": False,
                        "action": "set_login_account",
                        "error": "login ui not found",
                    }
                )
                return

            input_focus = getattr(ui, "input_account_focus", None)
            if input_focus is None:
                self._emit(
                    {
                        "ok": False,
                        "action": "set_login_account",
                        "ui_type": ui_type,
                        "error": "input_account_focus missing",
                    }
                )
                return

            if hasattr(input_focus, "set_txt"):
                input_focus.set_txt(account)
            elif hasattr(input_focus, "set_text"):
                input_focus.set_text(account)
            else:
                self._emit(
                    {
                        "ok": False,
                        "action": "set_login_account",
                        "ui_type": ui_type,
                        "error": "unsupported account input api",
                    }
                )
                return

            self._emit(
                {
                    "ok": True,
                    "action": "set_login_account",
                    "ui_type": ui_type,
                    "account": account,
                }
            )
        except Exception as exc:
            self._emit(
                {
                    "ok": False,
                    "action": "set_login_account",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    def login_with_profile(
        self,
        profile="trunk",
        space_type=2,
        spaceno=98121,
        ship_config_id=9,
        account="",
    ):
        try:
            from utils.debug.gpm.land_scene_builder.data.server_config import server_config_dict

            cfg = server_config_dict.get(profile, server_config_dict.get("trunk", {}))
            server_name = cfg["server_name"]
            server_ip = cfg["server_ip"]
            server_port = cfg["server_port"]
            gm_port = cfg.get("gm_port", server_port)
            server_index = cfg.get("server_index", 1)
            hostnum = cfg["hostnum"]
            if not account:
                self._emit(
                    {
                        "ok": False,
                        "action": "login_with_profile",
                        "error": "account_required",
                        "message": "account is required for profile login",
                        "profile": profile,
                    }
                )
                return

            _game_operator_instance.login_with_full_params(
                int(space_type),
                int(spaceno),
                int(ship_config_id),
                account,
                server_name,
                server_ip,
                int(server_port),
                int(gm_port),
                str(server_index),
                int(hostnum),
            )
            self._emit(
                {
                    "ok": True,
                    "action": "login_with_profile",
                    "profile": profile,
                    "space_type": space_type,
                    "spaceno": spaceno,
                    "ship_config_id": ship_config_id,
                    "account": account,
                    "server_ip": server_ip,
                    "server_port": server_port,
                    "gm_port": gm_port,
                }
            )
        except Exception as exc:
            self._emit(
                {
                    "ok": False,
                    "action": "login_with_profile",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    def check_login_ready(self):
        try:
            state = self._inspect_login_state()
            self._emit(
                {
                    "ok": True,
                    "action": "check_login_ready",
                    "ready": bool(state.get("ready")),
                    "space_no": state.get("space_no"),
                    "loading_type": state.get("loading_type"),
                    "controlled": state.get("controlled"),
                }
            )
        except Exception as exc:
            self._emit(
                {
                    "ok": False,
                    "action": "check_login_ready",
                    "ready": False,
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    def _load_nbs_test(self):
        if self._nbs_loaded_path != self.nbs_demo_path or self._nbs_script_env is None:
            env = {"__builtins__": __builtins__, "__name__": "__main__", "__file__": self.nbs_demo_path}
            with open(self.nbs_demo_path, "rb") as fp:
                code = compile(fp.read(), self.nbs_demo_path, "exec")
            exec(code, env, env)
            if "NBSTest" not in env:
                raise RuntimeError("NBSTest_missing_in_demo_script")
            self._nbs_script_env = env
            self._nbs_loaded_path = self.nbs_demo_path
        nbs_test = self._nbs_script_env["NBSTest"]()
        self._apply_nbs_play_args(nbs_test)
        return nbs_test

    def _apply_nbs_play_args(self, nbs_test):
        args = self._nbs_play_args or {}
        montid = args.get("montid")
        nbs = args.get("nbs")
        start = args.get("start")
        end = args.get("end")
        use_audio_sync = args.get("use_audio_sync")

        if montid is not None and hasattr(nbs_test, "montID"):
            try:
                nbs_test.montID = str(montid)
            except Exception:
                pass
        if nbs is not None and hasattr(nbs_test, "nbsPath"):
            try:
                nbs_test.nbsPath = str(nbs)
            except Exception:
                pass
        if start is not None and hasattr(nbs_test, "frameStartCount"):
            try:
                nbs_test.frameStartCount = int(start)
            except Exception:
                pass
        if use_audio_sync is not None and hasattr(nbs_test, "use_audio_sync"):
            try:
                nbs_test.use_audio_sync = bool(use_audio_sync)
            except Exception:
                pass

        self._install_end_frame_guard(nbs_test, end)

    @staticmethod
    def _install_end_frame_guard(nbs_test, end_frame):
        if end_frame in (None, "", 0):
            return
        try:
            end_frame = int(end_frame)
        except Exception:
            return

        original_update_cb = getattr(nbs_test, "UpdateCB", None)
        if original_update_cb is None:
            return
        if getattr(nbs_test, "_auto_end_frame_guard_installed", False):
            return

        nbs_test._auto_end_frame_guard_installed = True
        nbs_test.__auto_end_frame = end_frame
        nbs_test.__auto_end_triggered = False

        def wrapped_update_cb(decoder_id, frame_count):
            if getattr(nbs_test, "__auto_end_triggered", False):
                return

            try:
                start_offset = int(getattr(nbs_test, "frameStartCount", 0) or 0)
                absolute_frame = int(frame_count) + start_offset
                if absolute_frame >= int(getattr(nbs_test, "__auto_end_frame", end_frame)):
                    nbs_test.__auto_end_triggered = True
                    for fn in ("stopMont", "stopNBS", "stop"):
                        try:
                            getattr(nbs_test, fn)()
                        except Exception:
                            pass
                    return
            except Exception:
                pass

            return original_update_cb(decoder_id, frame_count)

        nbs_test.UpdateCB = wrapped_update_cb

    @staticmethod
    def _get_running_scene():
        import cc

        director = cc.Director.getInstance()
        if not director:
            raise RuntimeError("director_missing")
        scene = director.getRunningScene()
        if not scene:
            raise RuntimeError("running_scene_missing")
        return scene

    @staticmethod
    def _ensure_nbs_frame_tracking(nbs_test):
        if getattr(nbs_test, "_auto_updatecb_wrapped", False):
            return
        original_cb = getattr(nbs_test, "UpdateCB", None)
        if original_cb is None:
            return

        def _wrapped_updatecb(decoder_id, frame_count):
            try:
                nbs_test._auto_last_nbs_frame = int(frame_count)
                nbs_test._auto_last_actual_frame = int(getattr(nbs_test, "playStartFrame", 0)) + int(frame_count)
            except Exception:
                pass
            return original_cb(decoder_id, frame_count)

        nbs_test.UpdateCB = _wrapped_updatecb
        nbs_test._auto_updatecb_wrapped = True

    @staticmethod
    def _capture_renderdoc(frames=1, launch_replay_ui=False):
        import MRenderDoc

        frames = max(1, int(frames or 1))
        launch_replay_ui = bool(launch_replay_ui)
        if hasattr(MRenderDoc, "CaptureEx"):
            MRenderDoc.CaptureEx(frames, launch_replay_ui)
            return "CaptureEx"
        if frames == 1 and (not launch_replay_ui) and hasattr(MRenderDoc, "CaptureWithoutOpen"):
            MRenderDoc.CaptureWithoutOpen()
            return "CaptureWithoutOpen"
        MRenderDoc.Capture()
        return "Capture"

    def start_nbs_playback_with_capture(
        self,
        capture_mode="immediate",
        delay_frames=0,
        target_frame=0,
        frame_mode="nbs",
        capture_window_size=5,
        capture_pre_roll=2,
    ):
        try:
            capture_mode = str(capture_mode or "immediate")
            if capture_mode == "target_frame_single":
                capture_mode = "target_frame"
            if capture_mode not in ("immediate", "playing_delay_frames", "target_frame", "target_window"):
                raise ValueError("unsupported capture_mode: %s" % capture_mode)
            delay_frames = int(delay_frames or 0)
            target_frame = int(target_frame or 0)
            frame_mode = str(frame_mode or "nbs")
            if frame_mode not in ("nbs", "actual"):
                raise ValueError("unsupported frame_mode: %s" % frame_mode)
            capture_window_size = max(1, int(capture_window_size or 1))
            capture_pre_roll = max(0, int(capture_pre_roll or 0))

            nbs_test = self._load_nbs_test()
            self._ensure_nbs_frame_tracking(nbs_test)
            nbs_test.startPre()

            capture_done = False
            capture_api = ""
            if capture_mode == "immediate":
                capture_api = self._capture_renderdoc(frames=1, launch_replay_ui=False)
                capture_done = True

            self._scenario_state = {
                "name": "nbs_playback",
                "obj": nbs_test,
                "started_at": time.time(),
                "recording_seen": False,
                "playing_seen": False,
                "capture_mode": capture_mode,
                "capture_delay_frames": delay_frames,
                "capture_target_frame": target_frame,
                "capture_frame_mode": frame_mode,
                "capture_window_size": capture_window_size,
                "capture_pre_roll": capture_pre_roll,
                "capture_done": capture_done,
                "capture_api": capture_api,
                "capture_trigger_frame": None,
                "capture_triggered_at_frame": None,
                "capture_error": "",
                "capture_frame_cursor": 0,
                "capture_start_frame": None,
            }
            self._emit(
                {
                    "ok": True,
                    "action": "start_nbs_playback_with_capture",
                    "scenario": "nbs_playback",
                    "status": "started",
                    "capture_requested": True,
                    "capture_mode": capture_mode,
                    "capture_delay_frames": delay_frames,
                    "capture_target_frame": target_frame,
                    "capture_frame_mode": frame_mode,
                    "capture_window_size": capture_window_size,
                    "capture_pre_roll": capture_pre_roll,
                }
            )
        except Exception as exc:
            self._scenario_state = None
            self._emit(
                {
                    "ok": False,
                    "action": "start_nbs_playback_with_capture",
                    "scenario": "nbs_playback",
                    "status": "failed",
                    "capture_requested": True,
                    "capture_mode": str(capture_mode or ""),
                    "capture_target_frame": int(target_frame or 0),
                    "capture_frame_mode": str(frame_mode or ""),
                    "capture_window_size": int(capture_window_size or 0),
                    "capture_pre_roll": int(capture_pre_roll or 0),
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    def start_scenario(self, scenario):
        try:
            scenario = str(scenario)
            if scenario == "aov_record":
                nbs_test = self._load_nbs_test()
                nbs_test.AOVPre()
                self._scenario_state = {
                    "name": scenario,
                    "obj": nbs_test,
                    "started_at": time.time(),
                    "recording_seen": False,
                    "playing_seen": False,
                }
            elif scenario == "nbs_playback":
                nbs_test = self._load_nbs_test()
                nbs_test.startPre()
                self._scenario_state = {
                    "name": scenario,
                    "obj": nbs_test,
                    "started_at": time.time(),
                    "recording_seen": False,
                    "playing_seen": False,
                }
            else:
                raise ValueError("unsupported scenario: %s" % scenario)

            self._emit({"ok": True, "action": "start_scenario", "scenario": scenario, "status": "started"})
        except Exception as exc:
            self._scenario_state = None
            self._emit(
                {
                    "ok": False,
                    "action": "start_scenario",
                    "scenario": scenario,
                    "status": "failed",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    def poll_scenario(self):
        try:
            if not self._scenario_state:
                self._emit({"ok": True, "action": "poll_scenario", "status": "idle"})
                return

            scenario = self._scenario_state["name"]
            elapsed = time.time() - self._scenario_state["started_at"]

            if scenario == "aov_record":
                nbs_test = self._scenario_state["obj"]
                is_recording = bool(getattr(nbs_test, "isRecording", False))
                if is_recording:
                    self._scenario_state["recording_seen"] = True
                done = self._scenario_state["recording_seen"] and not is_recording
                if done:
                    self._scenario_state = None
                    self._emit(
                        {
                            "ok": True,
                            "action": "poll_scenario",
                            "scenario": scenario,
                            "status": "success",
                            "elapsed": round(elapsed, 2),
                        }
                    )
                else:
                    self._emit(
                        {
                            "ok": True,
                            "action": "poll_scenario",
                            "scenario": scenario,
                            "status": "running",
                            "elapsed": round(elapsed, 2),
                            "is_recording": is_recording,
                            "recording_seen": self._scenario_state["recording_seen"],
                        }
                    )
                return

            if scenario == "nbs_playback":
                nbs_test = self._scenario_state["obj"]
                mont_playing = bool(getattr(nbs_test, "montIsPlaying", False))
                decoder_id = int(getattr(nbs_test, "decoderID", -1))
                if mont_playing:
                    self._scenario_state["playing_seen"] = True
                if self._scenario_state.get("capture_mode") == "playing_delay_frames" and not self._scenario_state.get(
                    "capture_done", False
                ):
                    if mont_playing:
                        try:
                            import cc

                            director = cc.Director.getInstance()
                            total_frames = int(director.getTotalFrames())
                        except Exception:
                            total_frames = None
                        start_frame = self._scenario_state.get("capture_start_frame")
                        if start_frame is None and total_frames is not None:
                            self._scenario_state["capture_start_frame"] = total_frames
                            start_frame = total_frames
                        if start_frame is not None and total_frames is not None:
                            if (total_frames - start_frame) >= int(self._scenario_state.get("capture_delay_frames", 0)):
                                try:
                                    capture_api = self._capture_renderdoc(frames=1, launch_replay_ui=False)
                                    self._scenario_state["capture_done"] = True
                                    self._scenario_state["capture_api"] = capture_api
                                except Exception as exc:
                                    self._scenario_state["capture_error"] = repr(exc)
                                    # keep trying in next poll
                                    pass
                if self._scenario_state.get("capture_mode") in ("target_frame", "target_window") and not self._scenario_state.get(
                    "capture_done", False
                ):
                    if mont_playing:
                        capture_mode = self._scenario_state.get("capture_mode")
                        frame_mode = self._scenario_state.get("capture_frame_mode", "nbs")
                        target_frame = int(self._scenario_state.get("capture_target_frame", 0))
                        capture_pre_roll = int(self._scenario_state.get("capture_pre_roll", 0))
                        if capture_mode == "target_frame":
                            capture_pre_roll = 0
                        capture_trigger_frame = max(0, target_frame - capture_pre_roll)
                        self._scenario_state["capture_trigger_frame"] = capture_trigger_frame
                        current_frame = None
                        if frame_mode == "actual":
                            current_frame = getattr(nbs_test, "_auto_last_actual_frame", None)
                        else:
                            current_frame = getattr(nbs_test, "_auto_last_nbs_frame", None)
                        if current_frame is not None:
                            self._scenario_state["capture_frame_cursor"] = int(current_frame)
                        if current_frame is not None and int(current_frame) >= capture_trigger_frame:
                            try:
                                capture_window_size = int(self._scenario_state.get("capture_window_size", 1))
                                if capture_mode == "target_frame":
                                    capture_window_size = 1
                                capture_api = self._capture_renderdoc(frames=capture_window_size, launch_replay_ui=False)
                                self._scenario_state["capture_done"] = True
                                self._scenario_state["capture_api"] = capture_api
                                self._scenario_state["capture_triggered_at_frame"] = int(current_frame)
                            except Exception as exc:
                                self._scenario_state["capture_error"] = repr(exc)
                                pass
                done = self._scenario_state["playing_seen"] and (not mont_playing) and decoder_id == -1
                if done:
                    capture_mode = self._scenario_state.get("capture_mode", "")
                    capture_done = bool(self._scenario_state.get("capture_done", False))
                    capture_api = self._scenario_state.get("capture_api", "")
                    capture_trigger_frame = self._scenario_state.get("capture_trigger_frame", None)
                    capture_triggered_at_frame = self._scenario_state.get("capture_triggered_at_frame", None)
                    capture_error = self._scenario_state.get("capture_error", "")
                    self._scenario_state = None
                    self._emit(
                        {
                            "ok": True,
                            "action": "poll_scenario",
                            "scenario": scenario,
                            "status": "success",
                            "elapsed": round(elapsed, 2),
                            "capture_mode": capture_mode,
                            "capture_done": capture_done,
                            "capture_api": capture_api,
                            "capture_trigger_frame": capture_trigger_frame,
                            "capture_triggered_at_frame": capture_triggered_at_frame,
                            "capture_error": capture_error,
                        }
                    )
                else:
                    self._emit(
                        {
                            "ok": True,
                            "action": "poll_scenario",
                            "scenario": scenario,
                            "status": "running",
                            "elapsed": round(elapsed, 2),
                            "mont_playing": mont_playing,
                            "playing_seen": self._scenario_state["playing_seen"],
                            "decoder_id": decoder_id,
                            "capture_mode": self._scenario_state.get("capture_mode", ""),
                            "capture_done": bool(self._scenario_state.get("capture_done", False)),
                            "capture_api": self._scenario_state.get("capture_api", ""),
                            "capture_trigger_frame": self._scenario_state.get("capture_trigger_frame", None),
                            "capture_triggered_at_frame": self._scenario_state.get("capture_triggered_at_frame", None),
                            "capture_error": self._scenario_state.get("capture_error", ""),
                            "capture_frame_cursor": self._scenario_state.get("capture_frame_cursor", None),
                        }
                    )
                return

            self._scenario_state = None
            self._emit(
                {
                    "ok": False,
                    "action": "poll_scenario",
                    "scenario": scenario,
                    "status": "failed",
                    "error": "unsupported scenario",
                }
            )
        except Exception as exc:
            self._scenario_state = None
            self._emit(
                {
                    "ok": False,
                    "action": "poll_scenario",
                    "status": "failed",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    def request_exit(self):
        try:
            _game_operator_instance.exit()
            self._emit({"ok": True, "action": "request_exit"})
        except Exception as exc:
            self._emit({"ok": False, "action": "request_exit", "error": repr(exc)})


_auto_loop_operator = AutoLoopOperator()
print("Load Auto Loop Operator Success")
