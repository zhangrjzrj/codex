import json
import time
import traceback


class MiniGifReproOperator:
    def __init__(self):
        self._state = None
        self.minigif_path = r"F:/messiah_h74/820_complete.nbs"
        self.switch_minigif_path = r"F:/messiah_h74/820_complete.nbs"

    def _emit(self, payload):
        print("AUTO_JSON::" + json.dumps(payload, ensure_ascii=False))
        print("AUTO_END")

    def ping(self):
        self._emit({"ok": True, "action": "ping"})

    def set_minigif_path(self, path):
        self.minigif_path = str(path)
        self._emit({"ok": True, "action": "set_minigif_path", "path": self.minigif_path})

    def set_switch_minigif_path(self, path):
        self.switch_minigif_path = str(path)
        self._emit({"ok": True, "action": "set_switch_minigif_path", "path": self.switch_minigif_path})

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
    def _destroy_node(scene, active_holder, stats, old_node, reason, clear_external_resources):
        if old_node is None:
            return
        try:
            old_node.stop(bool(clear_external_resources))
            stats["stop_calls"] += 1
        except Exception as exc:
            stats["exceptions"].append("stop[%s]=%r" % (reason, exc))
        try:
            old_node.removeFromParent()
            stats["removed_before_create"] += 1
        except Exception as exc:
            stats["exceptions"].append("remove[%s]=%r" % (reason, exc))
        try:
            active_holder["nodes"].remove(old_node)
        except ValueError:
            pass

    def _run_one_replace_step(self, state):
        import cc

        scene = state["scene"]
        stats = state["stats"]
        active_holder = state["active_holder"]
        index = int(state["next_index"])
        mode = str(state.get("mode") or "seek_guard")
        if index >= int(state["total_rounds"]):
            return False

        holder = {"node": None}

        def _ready_cb(*_args):
            stats["ready_callbacks"] += 1

        node = cc.MiniGifNode.create(
            state["minigif_path"],
            False,
            0,
            False,
            _ready_cb,
            "",
            True,
        )
        holder["node"] = node
        active_holder["nodes"].append(node)
        if len(active_holder["nodes"]) > stats["max_live_nodes"]:
            stats["max_live_nodes"] = len(active_holder["nodes"])
        stats["created"] += 1

        size = cc.Director.getInstance().getOpenGLView().getDesignResolutionSize()
        node.setContentSize(size)
        node.setAnchorPoint(cc.Vec2(0.5, 0.5))
        node.setPosition(size.width * 0.5, size.height * 0.5)
        node.setName("%s_%s" % (state["remove_name"], index))
        node.setVisible(True)
        scene.addChild(node)

        if state["wait_decoder_ready"]:
            deadline = time.time() + (int(state["wait_decoder_timeout_ms"]) / 1000.0)
            decoder_ready = False
            while time.time() < deadline:
                try:
                    if int(node.getDecoderId()) >= 0:
                        decoder_ready = True
                        stats["decoder_ready_hits"] += 1
                        break
                except Exception:
                    pass
                time.sleep(0.01)
            if not decoder_ready:
                stats["decoder_ready_timeouts"] += 1

        if int(state["play_before_seek_ms"]) > 0:
            time.sleep(int(state["play_before_seek_ms"]) / 1000.0)

        if mode == "switch_guard":
            try:
                switch_result = node.switchToFile(
                    state["switch_minigif_path"],
                    False,
                    0,
                    False,
                    "",
                    True,
                )
                stats["switch_attempts"] += 1
                if switch_result:
                    stats["switch_successes"] += 1
            except Exception as exc:
                stats["exceptions"].append("Switch[%s]=%r" % (index, exc))
        elif mode == "size_guard":
            stats["size_guard_steps"] += 1
        elif state["seek_before_remove"]:
            try:
                node.Seek(0.0, 2)
                stats["seek_attempts"] += 1
            except Exception as exc:
                stats["exceptions"].append("Seek[%s]=%r" % (index, exc))

        if int(state["post_ready_pause_ms"]) > 0:
            time.sleep(int(state["post_ready_pause_ms"]) / 1000.0)

        if state["wait_decoder_ready"] and state["seek_before_remove"] and mode == "seek_guard":
            try:
                if int(node.getDecoderId()) >= 0:
                    node.Seek(0.0, 2)
                    stats["post_ready_seek_attempts"] += 1
            except Exception as exc:
                stats["exceptions"].append("PostReadySeek[%s]=%r" % (index, exc))

        if int(state["pause_ms"]) > 0:
            time.sleep(int(state["pause_ms"]) / 1000.0)

        if state["keep_only_latest"]:
            while len(active_holder["nodes"]) > int(state["overlap_nodes"]):
                self._destroy_node(
                    scene,
                    active_holder,
                    stats,
                    active_holder["nodes"][0],
                    "replace",
                    state["clear_external_resources"],
                )

        state["next_index"] = index + 1
        return True

    def start_replace_stress(
        self,
        file_path="",
        total_rounds=300,
        seek_before_remove=True,
        pause_ms=0,
        keep_only_latest=True,
        clear_external_resources=True,
        remove_name="gifNode",
        cleanup_after_finish=True,
        wait_decoder_ready=True,
        wait_decoder_timeout_ms=800,
        post_ready_pause_ms=0,
        overlap_nodes=2,
        steps_per_poll=1,
        play_before_seek_ms=1000,
        mode="seek_guard",
        switch_file_path="",
    ):
        try:
            file_path = str(file_path or self.minigif_path)
            switch_file_path = str(switch_file_path or self.switch_minigif_path or file_path)
            total_rounds = max(1, int(total_rounds or 1))
            pause_ms = max(0, int(pause_ms or 0))
            remove_name = str(remove_name or "gifNode")
            cleanup_after_finish = bool(cleanup_after_finish)
            wait_decoder_ready = bool(wait_decoder_ready)
            wait_decoder_timeout_ms = max(0, int(wait_decoder_timeout_ms or 0))
            post_ready_pause_ms = max(0, int(post_ready_pause_ms or 0))
            overlap_nodes = max(1, int(overlap_nodes or 1))
            steps_per_poll = max(1, int(steps_per_poll or 1))
            play_before_seek_ms = max(0, int(play_before_seek_ms or 0))
            mode = str(mode or "seek_guard").strip().lower()
            if mode not in ("size_guard", "seek_guard", "read_guard", "switch_guard"):
                raise RuntimeError("unsupported_mode:%s" % mode)
            scene = self._get_running_scene()

            stats = {
                "created": 0,
                "removed_before_create": 0,
                "ready_callbacks": 0,
                "seek_attempts": 0,
                "decoder_ready_hits": 0,
                "decoder_ready_timeouts": 0,
                "post_ready_seek_attempts": 0,
                "stop_calls": 0,
                "max_live_nodes": 0,
                "ready_callback_wait_hits": 0,
                "size_guard_steps": 0,
                "switch_attempts": 0,
                "switch_successes": 0,
                "exceptions": [],
            }
            active_holder = {"nodes": []}

            if mode == "size_guard":
                seek_before_remove = False
                wait_decoder_ready = False
                play_before_seek_ms = 0
            elif mode == "read_guard":
                seek_before_remove = False
                wait_decoder_ready = False
                if play_before_seek_ms <= 0:
                    play_before_seek_ms = 1000
            elif mode == "switch_guard":
                seek_before_remove = False
                wait_decoder_ready = False
                if play_before_seek_ms <= 0:
                    play_before_seek_ms = 100
            else:
                if play_before_seek_ms <= 0:
                    play_before_seek_ms = 0

            self._state = {
                "name": "minigif_replace_stress",
                "started_at": time.time(),
                "scene": scene,
                "minigif_path": file_path,
                "switch_minigif_path": switch_file_path,
                "total_rounds": total_rounds,
                "next_index": 0,
                "steps_per_poll": steps_per_poll,
                "seek_before_remove": bool(seek_before_remove),
                "pause_ms": pause_ms,
                "keep_only_latest": bool(keep_only_latest),
                "clear_external_resources": bool(clear_external_resources),
                "cleanup_after_finish": cleanup_after_finish,
                "wait_decoder_ready": wait_decoder_ready,
                "wait_decoder_timeout_ms": wait_decoder_timeout_ms,
                "play_before_seek_ms": play_before_seek_ms,
                "post_ready_pause_ms": post_ready_pause_ms,
                "overlap_nodes": overlap_nodes,
                "remove_name": remove_name,
                "mode": mode,
                "stats": stats,
                "active_holder": active_holder,
            }
            self._emit(
                {
                    "ok": True,
                    "action": "start_replace_stress",
                    "scenario": "minigif_replace_stress",
                    "status": "started",
                    "path": file_path,
                    "switch_path": switch_file_path,
                    "total_rounds": total_rounds,
                    "seek_before_remove": bool(seek_before_remove),
                    "pause_ms": pause_ms,
                    "keep_only_latest": bool(keep_only_latest),
                    "clear_external_resources": bool(clear_external_resources),
                    "cleanup_after_finish": cleanup_after_finish,
                    "wait_decoder_ready": wait_decoder_ready,
                    "wait_decoder_timeout_ms": wait_decoder_timeout_ms,
                    "play_before_seek_ms": play_before_seek_ms,
                    "post_ready_pause_ms": post_ready_pause_ms,
                    "overlap_nodes": overlap_nodes,
                    "steps_per_poll": steps_per_poll,
                    "mode": mode,
                    "remove_name": remove_name,
                }
            )
        except Exception as exc:
            self._state = None
            self._emit(
                {
                    "ok": False,
                    "action": "start_replace_stress",
                    "scenario": "minigif_replace_stress",
                    "status": "failed",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    def poll(self):
        try:
            if not self._state:
                self._emit({"ok": True, "action": "poll", "status": "idle"})
                return

            state = self._state
            stats = state["stats"]
            if state["name"] == "minigif_replace_stress":
                for _ in range(int(state.get("steps_per_poll", 1))):
                    if not self._run_one_replace_step(state):
                        break
                if int(state["next_index"]) >= int(state["total_rounds"]) and state["cleanup_after_finish"]:
                    for old_node in list(state["active_holder"]["nodes"]):
                        self._destroy_node(
                            state["scene"],
                            state["active_holder"],
                            stats,
                            old_node,
                            "final_cleanup",
                            state["clear_external_resources"],
                        )

            nodes = list(state["active_holder"].get("nodes", []))
            node = nodes[-1] if nodes else None
            alive = False
            decoder_id = -1
            has_parent = False
            if node is not None:
                try:
                    has_parent = node.getParent() is not None
                    decoder_id = int(node.getDecoderId())
                    alive = has_parent and decoder_id >= -1
                except Exception:
                    alive = False

            payload = {
                "ok": True,
                "action": "poll",
                "scenario": state["name"],
                "status": "running",
                "elapsed": round(time.time() - state["started_at"], 2),
                "next_index": int(state.get("next_index", 0)),
                "total_rounds": int(state.get("total_rounds", 0)),
                "created": int(stats.get("created", 0)),
                "removed_before_create": int(stats.get("removed_before_create", 0)),
                "ready_callbacks": int(stats.get("ready_callbacks", 0)),
                "seek_attempts": int(stats.get("seek_attempts", 0)),
                "decoder_ready_hits": int(stats.get("decoder_ready_hits", 0)),
                "decoder_ready_timeouts": int(stats.get("decoder_ready_timeouts", 0)),
                "post_ready_seek_attempts": int(stats.get("post_ready_seek_attempts", 0)),
                "size_guard_steps": int(stats.get("size_guard_steps", 0)),
                "switch_attempts": int(stats.get("switch_attempts", 0)),
                "switch_successes": int(stats.get("switch_successes", 0)),
                "stop_calls": int(stats.get("stop_calls", 0)),
                "max_live_nodes": int(stats.get("max_live_nodes", 0)),
                "remaining_nodes": len(nodes),
                "exceptions": list(stats.get("exceptions", []))[:20],
                "active_alive": bool(alive),
                "active_has_parent": bool(has_parent),
                "active_decoder_id": int(decoder_id),
                "mode": state.get("mode", "seek_guard"),
                "minigif_path": state.get("minigif_path", ""),
                "switch_minigif_path": state.get("switch_minigif_path", ""),
            }
            if int(state.get("next_index", 0)) >= int(state.get("total_rounds", 0)) and len(nodes) == 0:
                payload["status"] = "success"
                self._state = None
            self._emit(payload)
        except Exception as exc:
            self._state = None
            self._emit(
                {
                    "ok": False,
                    "action": "poll",
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
            self._emit({"ok": False, "action": "request_exit", "error": repr(exc), "traceback": traceback.format_exc()})


_minigif_repro_operator = MiniGifReproOperator()
print("Load MiniGif Repro Operator Success")
