#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import tempfile
import textwrap
import time
from datetime import datetime
from pathlib import Path


def str2bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_qrenderdoc(requested_path: str) -> Path:
    candidates: list[Path] = []
    if requested_path and str(requested_path).strip():
        candidates.append(Path(requested_path).expanduser())
    env_path = os.environ.get("RENDERDOC_QRENDERDOC", "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.extend(
        [
            Path(r"C:\Program Files\RenderDoc\qrenderdoc.exe"),
            Path(r"C:\Program Files (x86)\RenderDoc\qrenderdoc.exe"),
        ]
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    raise FileNotFoundError("qrenderdoc.exe not found; use --qrenderdoc-path or set RENDERDOC_QRENDERDOC")


def detect_renderdoc_version(qrenderdoc_path: Path) -> str:
    renderdoccmd = qrenderdoc_path.with_name("renderdoccmd.exe")
    if not renderdoccmd.exists():
        return ""
    try:
        proc = subprocess.run(
            [str(renderdoccmd), "version"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception:
        return ""
    text = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    match = re.search(r"v(\d+(?:\.\d+)*)", text)
    if match:
        return match.group(1)
    return text


def build_ui_script(config_b64: str) -> str:
    template = textwrap.dedent(
        r'''
        import base64
        import json
        import os
        import time
        import traceback
        import renderdoc as rd

        CONFIG_B64 = "__CONFIG_B64__"
        cfg = json.loads(base64.b64decode(CONFIG_B64.encode("ascii")).decode("utf-8"))
        output_json = cfg["output_json"]
        disasm_path = cfg["disasm_path"]
        ui_log_path = cfg["ui_log_path"]
        pass_keyword = str(cfg.get("pass_keyword", "") or "").strip()
        stage_name = str(cfg.get("stage", "pixel") or "pixel").strip().lower()
        disasm_lines = int(cfg.get("disasm_lines", 120))
        max_candidates = max(1, int(cfg.get("max_candidates", 30)))
        target_event_id = max(0, int(cfg.get("target_event_id", 0) or 0))
        target_var_name = str(cfg.get("target_var_name", "") or "").strip()
        prefer_target_var_nonzero = bool(cfg.get("prefer_target_var_nonzero", False))
        wait_timeout_sec = max(1.0, float(cfg.get("wait_timeout_sec", 60.0)))
        cb_value_mode = str(cfg.get("cb_value_mode", "layered") or "layered").strip().lower()
        cb_top_n = max(1, int(cfg.get("cb_top_n", 20)))
        cb_neighbor_window = max(0, int(cfg.get("cb_neighbor_window", 3)))
        cb_nonzero_only = bool(cfg.get("cb_nonzero_only", False))
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")

        result = {
            "created_at": now_iso,
            "status": "fail",
            "errors": [],
            "capture": {
                "path": cfg.get("rdc_path", ""),
                "api": "",
                "renderdoc_version": cfg.get("renderdoc_version", ""),
                "qrenderdoc_path": cfg.get("qrenderdoc_path", ""),
            },
            "target": {
                "event_id": 0,
                "action_id": 0,
                "custom_name": "",
                "stage": stage_name,
                "lock_mode": "event_id" if target_event_id > 0 else "auto",
                "requested_event_id": int(target_event_id),
                "resolved_event_id": 0,
                "auto_selected_reason": "",
            },
            "candidates": [],
            "pipeline": {
                "graphics_pipeline_id": "",
                "compute_pipeline_id": "",
                "d3d12_pipeline_resource_id": "",
                "root_signature_resource_id": "",
            },
            "shader": {
                "resource_id": "",
                "entry_point": "",
                "disasm_head": "",
                "disasm_full_path": "",
                "reflection_available": False,
            },
            "bindings": {
                "constant_blocks_meta": [],
                "constant_blocks_values_status": "empty",
                "constant_blocks_values_stats": {
                    "attempt_count": 0,
                    "fallback_hit_count": 0,
                    "success_block_count": 0,
                    "empty_block_count": 0,
                    "total_variable_count": 0,
                    "exported_variable_count": 0,
                    "nonzero_variable_count": 0,
                    "probe_mode": cb_value_mode,
                    "probe_neighbor_window": cb_neighbor_window,
                    "top_n": cb_top_n,
                    "nonzero_only": cb_nonzero_only,
                },
                "constant_blocks_values": [],
                "constant_blocks_bound": {"count": 0, "items": []},
                "read_only_resources": {"count": 0, "items": []},
                "read_write_resources": {"count": 0, "items": []},
                "descriptor_access_count": 0,
            },
        }
        logs = []

        def add_log(text):
            logs.append(str(text))

        def to_primitive(value):
            if value is None:
                return None
            if isinstance(value, (str, int, float, bool)):
                return value
            try:
                return int(value)
            except Exception:
                pass
            try:
                return float(value)
            except Exception:
                pass
            return str(value)

        def enum_stage(name):
            lowered = str(name).strip().lower()
            if lowered == "vertex":
                return rd.ShaderStage.Vertex
            if lowered == "compute":
                return rd.ShaderStage.Compute
            return rd.ShaderStage.Pixel

        def stage_probe_order(primary_stage, mode):
            all_stages = ["pixel", "vertex", "compute"]
            first = str(primary_stage or "pixel").strip().lower()
            ordered = [first]
            for stage in all_stages:
                if stage not in ordered:
                    ordered.append(stage)
            if mode == "strict":
                return [first]
            return ordered

        def event_probe_order(selected_event_id, candidate_rows, mode, neighbor_window):
            selected = int(selected_event_id or 0)
            event_ids = []
            for row in candidate_rows:
                try:
                    event_id = int(row.get("event_id", 0))
                except Exception:
                    event_id = 0
                if event_id > 0:
                    event_ids.append(event_id)
            event_ids = sorted(set(event_ids))
            if selected <= 0:
                selected = event_ids[0] if event_ids else 0
            if selected and selected not in event_ids:
                event_ids.append(selected)
                event_ids.sort()
            if mode == "strict":
                return [selected] if selected > 0 else []
            if not event_ids:
                return [selected] if selected > 0 else []
            index = 0
            try:
                index = event_ids.index(selected)
            except ValueError:
                index = 0
            if mode == "layered":
                left = max(0, index - int(neighbor_window))
                right = min(len(event_ids), index + int(neighbor_window) + 1)
                probe_ids = event_ids[left:right]
            else:
                probe_ids = event_ids
            probe_ids = sorted(probe_ids, key=lambda value: abs(value - selected))
            if selected > 0 and selected not in probe_ids:
                probe_ids.insert(0, selected)
            deduped = []
            seen = set()
            for event_id in probe_ids:
                if event_id in seen:
                    continue
                seen.add(event_id)
                deduped.append(event_id)
            return deduped

        def safe_numeric_list(values, limit):
            try:
                seq = list(values or [])
            except Exception:
                seq = []
            if limit <= 0:
                limit = len(seq)
            return [to_primitive(item) for item in seq[:limit]]

        def variable_shape(variable):
            rows = int(getattr(variable, "rows", 0) or 0)
            cols = int(getattr(variable, "columns", 0) or 0)
            var_type = getattr(variable, "type", None)
            if rows <= 0 and var_type is not None:
                rows = int(getattr(var_type, "rows", 0) or 0)
            if cols <= 0 and var_type is not None:
                cols = int(getattr(var_type, "columns", 0) or 0)
            if rows <= 0:
                rows = 1
            if cols <= 0:
                cols = 4
            count = rows * cols
            if count <= 0:
                count = 4
            count = max(1, min(16, count))
            return rows, cols, count

        def is_nonzero_values(f32_values, u32_values, s32_values):
            try:
                for value in f32_values:
                    if abs(float(value)) > 1e-8:
                        return True
            except Exception:
                pass
            try:
                for value in u32_values:
                    if int(value) != 0:
                        return True
            except Exception:
                pass
            try:
                for value in s32_values:
                    if int(value) != 0:
                        return True
            except Exception:
                pass
            return False

        def serialize_shader_variable(variable):
            rows, cols, value_limit = variable_shape(variable)
            value_obj = getattr(variable, "value", None)
            f32_values = safe_numeric_list(getattr(value_obj, "f32v", []), value_limit)
            u32_values = safe_numeric_list(getattr(value_obj, "u32v", []), value_limit)
            s32_values = safe_numeric_list(getattr(value_obj, "s32v", []), value_limit)
            is_nonzero = is_nonzero_values(f32_values, u32_values, s32_values)
            return {
                "name": str(getattr(variable, "name", "") or ""),
                "rows": int(rows),
                "cols": int(cols),
                "value_f32": f32_values,
                "value_u32": u32_values,
                "value_s32": s32_values,
                "is_nonzero": bool(is_nonzero),
            }

        def extract_cbuffer_values_once(controller, event_id, stage_probe, top_n, nonzero_only):
            stage_enum = enum_stage(stage_probe)
            controller.SetFrameEvent(int(event_id), True)
            pipe_state_local = controller.GetPipelineState()
            shader_refl_local = pipe_state_local.GetShaderReflection(stage_enum)
            if shader_refl_local is None:
                return {
                    "usable": False,
                    "reason": "no_shader_reflection",
                    "source_event_id": int(event_id),
                    "source_stage": str(stage_probe),
                    "blocks": [],
                    "stats": {
                        "success_block_count": 0,
                        "empty_block_count": 0,
                        "total_variable_count": 0,
                        "exported_variable_count": 0,
                        "nonzero_variable_count": 0,
                    },
                }

            constant_blocks_local = list(getattr(shader_refl_local, "constantBlocks", []) or [])
            if not constant_blocks_local:
                return {
                    "usable": False,
                    "reason": "no_constant_blocks",
                    "source_event_id": int(event_id),
                    "source_stage": str(stage_probe),
                    "blocks": [],
                    "stats": {
                        "success_block_count": 0,
                        "empty_block_count": 0,
                        "total_variable_count": 0,
                        "exported_variable_count": 0,
                        "nonzero_variable_count": 0,
                    },
                }

            shader_local = pipe_state_local.GetShader(stage_enum)
            entry_local = str(pipe_state_local.GetShaderEntryPoint(stage_enum))
            pipeline_local = (
                pipe_state_local.GetComputePipelineObject()
                if str(stage_probe).lower() == "compute"
                else pipe_state_local.GetGraphicsPipelineObject()
            )

            blocks = []
            success_block_count = 0
            empty_block_count = 0
            total_variable_count = 0
            exported_variable_count = 0
            nonzero_variable_count = 0

            for slot, block in enumerate(constant_blocks_local):
                bound = None
                try:
                    bound = pipe_state_local.GetConstantBlock(stage_enum, slot, 0)
                except Exception:
                    bound = None

                descriptor = getattr(bound, "descriptor", None) if bound is not None else None
                resource_id = rd.ResourceId.Null()
                byte_offset = 0
                descriptor_byte_size = 0
                if descriptor is not None:
                    resource_id = getattr(descriptor, "resource", rd.ResourceId.Null())
                    byte_offset = int(getattr(descriptor, "byteOffset", 0) or 0)
                    descriptor_byte_size = int(getattr(descriptor, "byteSize", 0) or 0)
                byte_length = int(getattr(block, "byteSize", 0) or 0)
                if byte_length <= 0 and descriptor_byte_size > 0:
                    byte_length = descriptor_byte_size
                if descriptor_byte_size > 0 and byte_length > descriptor_byte_size:
                    byte_length = descriptor_byte_size

                variables_raw = []
                block_error = ""
                try:
                    variables_raw = list(
                        controller.GetCBufferVariableContents(
                            pipeline_local,
                            shader_local,
                            stage_enum,
                            entry_local,
                            int(slot),
                            resource_id,
                            int(byte_offset),
                            int(byte_length),
                        )
                        or []
                    )
                except Exception as cb_exc:
                    block_error = repr(cb_exc)
                    variables_raw = []

                exported_variables = []
                block_nonzero = 0
                for variable in variables_raw:
                    row = serialize_shader_variable(variable)
                    if row["is_nonzero"]:
                        block_nonzero += 1
                    if nonzero_only and not row["is_nonzero"]:
                        continue
                    if len(exported_variables) < int(top_n):
                        exported_variables.append(row)

                variable_total = len(variables_raw)
                total_variable_count += variable_total
                nonzero_variable_count += block_nonzero
                exported_variable_count += len(exported_variables)
                has_values = variable_total > 0
                if has_values:
                    success_block_count += 1
                else:
                    empty_block_count += 1

                block_row = {
                    "slot": int(slot),
                    "name": str(getattr(block, "name", "") or ""),
                    "byte_size": byte_length,
                    "source_event_id": int(event_id),
                    "source_stage": str(stage_probe),
                    "buffer_resource_id": str(resource_id),
                    "descriptor_byte_size": int(descriptor_byte_size),
                    "byte_offset": int(byte_offset),
                    "byte_length": int(byte_length),
                    "has_values": bool(has_values),
                    "variable_count_total": int(variable_total),
                    "nonzero_variable_count": int(block_nonzero),
                    "variables": exported_variables,
                }
                if block_error:
                    block_row["error"] = block_error
                blocks.append(block_row)

            usable = exported_variable_count > 0 if bool(nonzero_only) else total_variable_count > 0
            return {
                "usable": bool(usable),
                "reason": "",
                "source_event_id": int(event_id),
                "source_stage": str(stage_probe),
                "blocks": blocks,
                "stats": {
                    "success_block_count": int(success_block_count),
                    "empty_block_count": int(empty_block_count),
                    "total_variable_count": int(total_variable_count),
                    "exported_variable_count": int(exported_variable_count),
                    "nonzero_variable_count": int(nonzero_variable_count),
                },
            }

        def find_variable_in_blocks(blocks, variable_name):
            needle = str(variable_name or "").strip()
            if not needle:
                return None
            for block in list(blocks or []):
                for variable in list(block.get("variables", []) or []):
                    if str(variable.get("name", "")) == needle:
                        return variable
            return None

        def walk_actions(actions, depth=0):
            for action in list(actions or []):
                yield action, depth
                children = []
                try:
                    children = list(action.children)
                except Exception:
                    children = []
                for child, child_depth in walk_actions(children, depth + 1):
                    yield child, child_depth

        def score_action(name_text):
            lowered = str(name_text).lower()
            score = 0
            if pass_keyword and pass_keyword.lower() in lowered:
                score += 200
            if "water" in lowered:
                score += 80
            if "primitive" in lowered:
                score += 40
            if "[shading]" in lowered:
                score += 30
            if "pass" in lowered:
                score += 10
            return score

        def serialize_descriptor_items(items, limit):
            values = list(items or [])
            serialized = []
            for idx, item in enumerate(values[:limit]):
                row = {
                    "slot": idx,
                    "repr": str(item),
                }
                for name in (
                    "access",
                    "descriptorStore",
                    "descriptor",
                    "resourceId",
                    "byteOffset",
                    "byteSize",
                    "index",
                    "arrayElement",
                ):
                    if hasattr(item, name):
                        try:
                            row[name] = to_primitive(getattr(item, name))
                        except Exception:
                            pass
                try:
                    descriptor = getattr(item, "descriptor", None)
                    if descriptor is not None:
                        row["descriptor_resource"] = to_primitive(getattr(descriptor, "resource", None))
                        row["descriptor_byte_offset"] = to_primitive(getattr(descriptor, "byteOffset", None))
                        row["descriptor_byte_size"] = to_primitive(getattr(descriptor, "byteSize", None))
                        row["descriptor_type"] = to_primitive(getattr(descriptor, "type", None))
                except Exception:
                    pass
                try:
                    access = getattr(item, "access", None)
                    if access is not None:
                        row["access_byte_offset"] = to_primitive(getattr(access, "byteOffset", None))
                        row["access_byte_size"] = to_primitive(getattr(access, "byteSize", None))
                        row["access_array_element"] = to_primitive(getattr(access, "arrayElement", None))
                        row["access_type"] = to_primitive(getattr(access, "type", None))
                except Exception:
                    pass
                serialized.append(row)
            return {"count": len(values), "items": serialized}

        def write_outputs():
            try:
                os.makedirs(os.path.dirname(output_json), exist_ok=True)
                with open(output_json, "w", encoding="utf-8") as fp:
                    json.dump(result, fp, ensure_ascii=False, indent=2)
            except Exception:
                pass
            try:
                os.makedirs(os.path.dirname(ui_log_path), exist_ok=True)
                with open(ui_log_path, "w", encoding="utf-8") as fp:
                    for line in logs:
                        fp.write(line + "\n")
            except Exception:
                pass

        try:
            add_log("ui_script_start")
            deadline = time.time() + wait_timeout_sec
            while time.time() < deadline:
                loaded = False
                try:
                    loaded = bool(pyrenderdoc.IsCaptureLoaded())
                except Exception:
                    loaded = False
                roots = []
                try:
                    roots = list(pyrenderdoc.CurRootActions() or [])
                except Exception:
                    roots = []
                if loaded and roots:
                    break
                time.sleep(0.1)

            root_actions = list(pyrenderdoc.CurRootActions() or [])
            add_log(f"root_count={len(root_actions)}")
            all_actions = []
            internal_candidates = []
            for action, depth in walk_actions(root_actions):
                custom_name = str(getattr(action, "customName", "") or "")
                lowered = custom_name.lower()
                action_row = {
                    "event_id": int(getattr(action, "eventId", 0) or 0),
                    "action_id": int(getattr(action, "actionId", 0) or 0),
                    "custom_name": custom_name,
                    "flags": int(getattr(action, "flags", 0) or 0),
                    "depth": int(depth),
                    "score": int(score_action(custom_name)),
                    "_name_lower": lowered,
                }
                all_actions.append(action_row)
                matched = False
                if pass_keyword:
                    if pass_keyword.lower() in lowered:
                        matched = True
                    elif "water" in lowered:
                        matched = True
                else:
                    if "water" in lowered:
                        matched = True
                if not matched:
                    continue
                internal_candidates.append(action_row)

            internal_candidates.sort(key=lambda row: (-row["score"], row["depth"], row["event_id"]))
            candidates = [{k: v for k, v in row.items() if k != "_name_lower"} for row in internal_candidates]
            result["candidates"] = candidates[:max_candidates]
            if target_event_id > 0:
                target = None
                for row in all_actions:
                    if int(row.get("event_id", 0)) == target_event_id:
                        target = row
                        break
                if target is None:
                    result["status"] = "fail"
                    result["errors"].append(f"target_event_not_found:{target_event_id}")
                    write_outputs()
                    os._exit(0)
                target_candidates = [target]
            else:
                if not internal_candidates:
                    result["status"] = "partial"
                    result["errors"].append("no_matching_event_candidates")
                    write_outputs()
                    os._exit(0)
                if prefer_target_var_nonzero and target_var_name:
                    target_candidates = internal_candidates
                else:
                    preferred = [
                        row
                        for row in internal_candidates
                        if "primitive" in row["_name_lower"] and "[shading]" in row["_name_lower"]
                    ]
                    target_candidates = preferred if preferred else internal_candidates
                target = target_candidates[0]
            result["target"]["event_id"] = target["event_id"]
            result["target"]["action_id"] = target["action_id"]
            result["target"]["custom_name"] = target["custom_name"]
            result["target"]["resolved_event_id"] = int(target["event_id"])

            replay_manager = pyrenderdoc.Replay()
            stage_enum = enum_stage(stage_name)

            def replay_callback(controller):
                selected_target = target
                selected_reason = "target_event_id_lock" if target_event_id > 0 else "auto_reflection_score"
                if target_event_id <= 0:
                    if prefer_target_var_nonzero and target_var_name:
                        best_var_score = None
                        for probe_target in target_candidates[:max_candidates]:
                            probe_payload = extract_cbuffer_values_once(
                                controller=controller,
                                event_id=int(probe_target["event_id"]),
                                stage_probe=stage_name,
                                top_n=max(cb_top_n, 256),
                                nonzero_only=False,
                            )
                            if not probe_payload.get("usable"):
                                continue
                            variable = find_variable_in_blocks(probe_payload.get("blocks", []), target_var_name)
                            if not variable:
                                continue
                            if not bool(variable.get("is_nonzero", False)):
                                continue
                            values = list(variable.get("value_f32", []) or [])
                            magnitude = 0.0
                            for value in values:
                                try:
                                    magnitude += abs(float(value))
                                except Exception:
                                    pass
                            score = (
                                1,
                                float(magnitude),
                                int(probe_target.get("event_id", 0)),
                            )
                            if best_var_score is None or score > best_var_score:
                                best_var_score = score
                                selected_target = probe_target
                                selected_reason = f"target_var_nonzero:{target_var_name}"
                    if selected_reason == "auto_reflection_score":
                        best_score = (-1, -1, -1)
                        for probe_target in target_candidates[:max_candidates]:
                            controller.SetFrameEvent(probe_target["event_id"], True)
                            probe_state = controller.GetPipelineState()
                            probe_refl = probe_state.GetShaderReflection(stage_enum)
                            probe_cb_count = len(list(getattr(probe_refl, "constantBlocks", []) or [])) if probe_refl is not None else 0
                            try:
                                probe_ro_count = len(list(probe_state.GetReadOnlyResources(stage_enum, False) or []))
                            except Exception:
                                probe_ro_count = 0
                            probe_score = (1 if probe_refl is not None else 0, int(probe_cb_count), int(probe_ro_count))
                            if probe_score > best_score:
                                best_score = probe_score
                                selected_target = probe_target
                controller.SetFrameEvent(selected_target["event_id"], True)
                result["target"]["event_id"] = int(selected_target["event_id"])
                result["target"]["action_id"] = int(selected_target["action_id"])
                result["target"]["custom_name"] = str(selected_target["custom_name"])
                result["target"]["resolved_event_id"] = int(selected_target["event_id"])
                result["target"]["auto_selected_reason"] = str(selected_reason)
                api_props = controller.GetAPIProperties()
                result["capture"]["api"] = str(getattr(api_props, "pipelineType", ""))
                pipe_state = controller.GetPipelineState()
                d3d12_state = controller.GetD3D12PipelineState()

                try:
                    result["pipeline"]["graphics_pipeline_id"] = str(pipe_state.GetGraphicsPipelineObject())
                except Exception:
                    result["pipeline"]["graphics_pipeline_id"] = ""
                try:
                    result["pipeline"]["compute_pipeline_id"] = str(pipe_state.GetComputePipelineObject())
                except Exception:
                    result["pipeline"]["compute_pipeline_id"] = ""
                try:
                    result["pipeline"]["d3d12_pipeline_resource_id"] = str(getattr(d3d12_state, "pipelineResourceId", ""))
                except Exception:
                    result["pipeline"]["d3d12_pipeline_resource_id"] = ""
                try:
                    root_signature = getattr(d3d12_state, "rootSignature", None)
                    root_sig_res = getattr(root_signature, "resourceId", "")
                    result["pipeline"]["root_signature_resource_id"] = str(root_sig_res)
                except Exception:
                    result["pipeline"]["root_signature_resource_id"] = ""

                shader_resource = pipe_state.GetShader(stage_enum)
                shader_entry = pipe_state.GetShaderEntryPoint(stage_enum)
                shader_refl = pipe_state.GetShaderReflection(stage_enum)
                result["shader"]["resource_id"] = str(shader_resource)
                result["shader"]["entry_point"] = str(shader_entry)
                result["shader"]["reflection_available"] = bool(shader_refl is not None)

                pipeline_for_disasm = pipe_state.GetComputePipelineObject() if stage_name == "compute" else pipe_state.GetGraphicsPipelineObject()
                if shader_refl is not None:
                    try:
                        disasm_text = controller.DisassembleShader(pipeline_for_disasm, shader_refl, "")
                    except Exception as disasm_exc:
                        disasm_text = ""
                        result["errors"].append(f"disassemble_failed:{disasm_exc!r}")
                    if disasm_text:
                        os.makedirs(os.path.dirname(disasm_path), exist_ok=True)
                        with open(disasm_path, "w", encoding="utf-8") as fp:
                            fp.write(disasm_text)
                        result["shader"]["disasm_full_path"] = disasm_path
                        result["shader"]["disasm_head"] = "\n".join(disasm_text.splitlines()[:disasm_lines])

                    constant_blocks = list(getattr(shader_refl, "constantBlocks", []) or [])
                    block_items = []
                    for slot, block in enumerate(constant_blocks):
                        variables = list(getattr(block, "variables", []) or [])
                        variable_preview = []
                        for variable in variables[:12]:
                            variable_preview.append(str(getattr(variable, "name", "") or ""))
                        block_items.append(
                            {
                                "slot": int(slot),
                                "name": str(getattr(block, "name", "") or ""),
                                "byte_size": int(getattr(block, "byteSize", 0) or 0),
                                "buffer_backed": bool(getattr(block, "bufferBacked", False)),
                                "variable_count": len(variables),
                                "variable_preview": variable_preview,
                            }
                        )
                    result["bindings"]["constant_blocks_meta"] = block_items
                else:
                    result["bindings"]["constant_blocks_meta"] = []

                try:
                    result["bindings"]["constant_blocks_bound"] = serialize_descriptor_items(
                        pipe_state.GetConstantBlocks(stage_enum, False), 64
                    )
                except Exception as exc:
                    result["errors"].append(f"constant_blocks_bound_failed:{exc!r}")
                    result["bindings"]["constant_blocks_bound"] = {"count": 0, "items": []}

                try:
                    result["bindings"]["read_only_resources"] = serialize_descriptor_items(
                        pipe_state.GetReadOnlyResources(stage_enum, False), 128
                    )
                except Exception as exc:
                    result["errors"].append(f"read_only_resources_failed:{exc!r}")
                    result["bindings"]["read_only_resources"] = {"count": 0, "items": []}

                try:
                    result["bindings"]["read_write_resources"] = serialize_descriptor_items(
                        pipe_state.GetReadWriteResources(stage_enum, False), 128
                    )
                except Exception as exc:
                    result["errors"].append(f"read_write_resources_failed:{exc!r}")
                    result["bindings"]["read_write_resources"] = {"count": 0, "items": []}

                try:
                    descriptor_access = list(controller.GetDescriptorAccess() or [])
                    result["bindings"]["descriptor_access_count"] = len(descriptor_access)
                except Exception:
                    result["bindings"]["descriptor_access_count"] = 0

                selected_event_id = int(selected_target["event_id"])
                if target_event_id > 0:
                    probe_events = [selected_event_id] if selected_event_id > 0 else []
                else:
                    probe_events = event_probe_order(
                        selected_event_id=selected_event_id,
                        candidate_rows=target_candidates,
                        mode=cb_value_mode,
                        neighbor_window=cb_neighbor_window,
                    )
                probe_stages = stage_probe_order(stage_name, cb_value_mode)
                attempt_count = 0
                fallback_hit_count = 0
                chosen_probe = None
                chosen_score = (-1, -1, -1)

                for probe_event in probe_events:
                    for probe_stage in probe_stages:
                        attempt_count += 1
                        probe_payload = extract_cbuffer_values_once(
                            controller=controller,
                            event_id=probe_event,
                            stage_probe=probe_stage,
                            top_n=cb_top_n,
                            nonzero_only=cb_nonzero_only,
                        )
                        if not probe_payload.get("usable"):
                            continue
                        probe_stats = probe_payload.get("stats", {})
                        probe_score = (
                            int(probe_stats.get("exported_variable_count", 0)),
                            int(probe_stats.get("nonzero_variable_count", 0)),
                            int(probe_stats.get("success_block_count", 0)),
                        )
                        if cb_value_mode == "aggressive":
                            if probe_score > chosen_score:
                                chosen_probe = probe_payload
                                chosen_score = probe_score
                            continue
                        chosen_probe = probe_payload
                        chosen_score = probe_score
                        break
                    if chosen_probe is not None and cb_value_mode != "aggressive":
                        break

                if chosen_probe is not None:
                    selected_source_event = int(chosen_probe.get("source_event_id", 0))
                    selected_source_stage = str(chosen_probe.get("source_stage", stage_name))
                    if selected_source_event != selected_event_id or selected_source_stage != stage_name:
                        fallback_hit_count = 1
                    bindings_stats = result["bindings"]["constant_blocks_values_stats"]
                    chosen_stats = chosen_probe.get("stats", {})
                    bindings_stats["attempt_count"] = int(attempt_count)
                    bindings_stats["fallback_hit_count"] = int(fallback_hit_count)
                    bindings_stats["success_block_count"] = int(chosen_stats.get("success_block_count", 0))
                    bindings_stats["empty_block_count"] = int(chosen_stats.get("empty_block_count", 0))
                    bindings_stats["total_variable_count"] = int(chosen_stats.get("total_variable_count", 0))
                    bindings_stats["exported_variable_count"] = int(chosen_stats.get("exported_variable_count", 0))
                    bindings_stats["nonzero_variable_count"] = int(chosen_stats.get("nonzero_variable_count", 0))
                    result["bindings"]["constant_blocks_values"] = list(chosen_probe.get("blocks", []))
                    if selected_source_event == selected_event_id and selected_source_stage == stage_name:
                        result["bindings"]["constant_blocks_values_status"] = "direct"
                    else:
                        result["bindings"]["constant_blocks_values_status"] = "fallback"
                else:
                    bindings_stats = result["bindings"]["constant_blocks_values_stats"]
                    bindings_stats["attempt_count"] = int(attempt_count)
                    bindings_stats["fallback_hit_count"] = 0
                    bindings_stats["success_block_count"] = 0
                    bindings_stats["empty_block_count"] = 0
                    bindings_stats["total_variable_count"] = 0
                    bindings_stats["exported_variable_count"] = 0
                    bindings_stats["nonzero_variable_count"] = 0
                    result["bindings"]["constant_blocks_values_status"] = "empty"
                    result["bindings"]["constant_blocks_values"] = []

            replay_manager.BlockInvoke(replay_callback)

            if result["target"]["event_id"] <= 0:
                result["status"] = "partial"
                result["errors"].append("target_event_invalid")
            elif result["shader"]["disasm_head"]:
                result["status"] = "success"
            else:
                result["status"] = "partial"
                result["errors"].append("shader_disasm_empty")
            if result["status"] == "success" and result["errors"]:
                result["status"] = "partial"
            add_log(f"status={result['status']}")
        except Exception as exc:
            result["status"] = "fail"
            result["errors"].append(f"exception:{exc!r}")
            result["errors"].append(traceback.format_exc())
            add_log(f"fatal_exception={exc!r}")
        finally:
            write_outputs()
            os._exit(0)
        '''
    )
    return template.replace("__CONFIG_B64__", config_b64)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RenderDoc offline analyzer for Messiah test loop")
    parser.add_argument("--rdc-path", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, default=Path(""))
    parser.add_argument("--pass-keyword", default="WaterPass")
    parser.add_argument("--stage", choices=["pixel", "vertex", "compute"], default="pixel")
    parser.add_argument("--qrenderdoc-path", default="")
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--disasm-lines", type=int, default=120)
    parser.add_argument("--max-candidates", type=int, default=30)
    parser.add_argument("--target-event-id", type=int, default=0)
    parser.add_argument("--target-var-name", default="")
    parser.add_argument("--prefer-target-var-nonzero", type=str2bool, default=False)
    parser.add_argument("--cb-value-mode", choices=["layered", "strict", "aggressive"], default="layered")
    parser.add_argument("--cb-top-n", type=int, default=20)
    parser.add_argument("--cb-neighbor-window", type=int, default=3)
    parser.add_argument("--cb-nonzero-only", type=str2bool, default=False)
    parser.add_argument("--fail-on-partial", type=str2bool, default=False)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    rdc_path = args.rdc_path.resolve()
    if not rdc_path.exists():
        raise FileNotFoundError(f"rdc file not found: {rdc_path}")

    output_json = args.output_json.resolve() if str(args.output_json).strip() else rdc_path.with_suffix(".rdc_analysis.json")
    disasm_path = output_json.with_suffix(".disasm.txt")
    ui_log_path = output_json.with_suffix(".ui.log")
    output_json.parent.mkdir(parents=True, exist_ok=True)

    if output_json.exists():
        output_json.unlink()
    if disasm_path.exists():
        disasm_path.unlink()
    if ui_log_path.exists():
        ui_log_path.unlink()

    qrenderdoc_path = detect_qrenderdoc(args.qrenderdoc_path)
    renderdoc_version = detect_renderdoc_version(qrenderdoc_path)

    cfg = {
        "rdc_path": str(rdc_path),
        "output_json": str(output_json),
        "disasm_path": str(disasm_path),
        "ui_log_path": str(ui_log_path),
        "pass_keyword": args.pass_keyword,
        "stage": args.stage,
        "disasm_lines": int(args.disasm_lines),
        "max_candidates": int(args.max_candidates),
        "target_event_id": max(0, int(args.target_event_id)),
        "target_var_name": str(args.target_var_name or "").strip(),
        "prefer_target_var_nonzero": bool(args.prefer_target_var_nonzero),
        "cb_value_mode": str(args.cb_value_mode),
        "cb_top_n": max(1, int(args.cb_top_n)),
        "cb_neighbor_window": max(0, int(args.cb_neighbor_window)),
        "cb_nonzero_only": bool(args.cb_nonzero_only),
        "wait_timeout_sec": max(15, int(args.timeout_sec)),
        "renderdoc_version": renderdoc_version,
        "qrenderdoc_path": str(qrenderdoc_path),
    }
    config_b64 = base64.b64encode(json.dumps(cfg, ensure_ascii=False).encode("utf-8")).decode("ascii")
    ui_script_content = build_ui_script(config_b64)

    fd, ui_script_path_raw = tempfile.mkstemp(prefix="rdc_ui_analyze_", suffix=".py")
    os.close(fd)
    ui_script_path = Path(ui_script_path_raw).resolve()
    ui_script_path.write_text(ui_script_content, encoding="utf-8")

    proc: subprocess.Popen[str] | None = None
    stdout_text = ""
    stderr_text = ""
    start_ts = time.time()
    run_log_path = output_json.with_suffix(".runner.log")
    output_ready = False

    def is_output_json_ready(path: Path) -> bool:
        if not path.exists():
            return False
        try:
            raw = path.read_text(encoding="utf-8")
            json.loads(raw)
            return True
        except Exception:
            return False

    try:
        cmd = [str(qrenderdoc_path), "--ui-python", str(ui_script_path), str(rdc_path)]
        proc = subprocess.Popen(
            cmd,
            cwd=str(rdc_path.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = start_ts + max(30, int(args.timeout_sec))
        while time.time() < deadline:
            if is_output_json_ready(output_json):
                output_ready = True
                break
            if proc.poll() is not None:
                output_ready = is_output_json_ready(output_json)
                if output_ready:
                    break
            time.sleep(0.2)

        if proc.poll() is None and output_ready:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        elif proc.poll() is None and not output_json.exists():
            proc.kill()

        try:
            out, err = proc.communicate(timeout=5) if proc else ("", "")
            stdout_text = out or ""
            stderr_text = err or ""
        except Exception:
            stdout_text = ""
            stderr_text = ""
    finally:
        try:
            ui_script_path.unlink(missing_ok=True)
        except Exception:
            pass

    if not output_json.exists():
        fallback = {
            "created_at": datetime.now().isoformat(),
            "status": "fail",
            "errors": ["output_json_missing_after_qrenderdoc"],
            "capture": {
                "path": str(rdc_path),
                "api": "",
                "renderdoc_version": renderdoc_version,
                "qrenderdoc_path": str(qrenderdoc_path),
            },
            "target": {
                "event_id": 0,
                "action_id": 0,
                "custom_name": "",
                "stage": args.stage,
                "lock_mode": "event_id" if int(args.target_event_id) > 0 else "auto",
                "requested_event_id": max(0, int(args.target_event_id)),
                "resolved_event_id": 0,
                "auto_selected_reason": "",
            },
            "candidates": [],
            "pipeline": {},
            "shader": {},
            "bindings": {},
        }
        write_json(output_json, fallback)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    payload.setdefault("capture", {})
    payload["capture"]["renderdoc_version"] = payload["capture"].get("renderdoc_version") or renderdoc_version
    payload["capture"]["qrenderdoc_path"] = payload["capture"].get("qrenderdoc_path") or str(qrenderdoc_path)
    payload["runner"] = {
        "duration_sec": round(max(0.0, time.time() - start_ts), 3),
        "rdc_path": str(rdc_path),
        "output_json": str(output_json),
        "ui_log_path": str(ui_log_path),
        "runner_log_path": str(run_log_path),
    }
    write_json(
        run_log_path,
        {
            "cmd": [str(qrenderdoc_path), "--ui-python", str(ui_script_path), str(rdc_path)],
            "stdout": stdout_text,
            "stderr": stderr_text,
            "finished_at": datetime.now().isoformat(),
        },
    )
    write_json(output_json, payload)

    status = str(payload.get("status", "fail")).lower()
    print(f"status={status}")
    print(f"output_json={output_json}")
    print(f"ui_log_path={ui_log_path}")
    disasm_output = payload.get("shader", {}).get("disasm_full_path", "")
    if disasm_output:
        print(f"disasm_full_path={disasm_output}")

    if status == "fail":
        return 1
    if status == "partial" and args.fail_on_partial:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
