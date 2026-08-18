#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import subprocess
import tempfile
import textwrap
import time
from datetime import datetime
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_version_tuple(version_text: str) -> tuple[int, ...]:
    parts = [int(p) for p in re.findall(r"\d+", version_text or "")]
    return tuple(parts) if parts else (0,)


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
    return match.group(1) if match else text


def detect_qrenderdoc(requested_path: str) -> tuple[Path, str, list[dict]]:
    if requested_path and requested_path.strip():
        resolved = Path(requested_path).expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"explicit qrenderdoc.exe not found: {resolved}")
        version = detect_renderdoc_version(resolved)
        return resolved, "explicit_argument", [
            {"path": str(resolved), "version": version, "source": "explicit_argument", "selected": True}
        ]

    candidates: list[tuple[str, Path]] = []
    env_path = os.environ.get("RENDERDOC_QRENDERDOC", "").strip()
    if env_path:
        candidates.append(("env:RENDERDOC_QRENDERDOC", Path(env_path).expanduser()))
    candidates.extend(
        [
            ("system_program_files", Path(r"C:\Program Files\RenderDoc\qrenderdoc.exe")),
            ("system_program_files_x86", Path(r"C:\Program Files (x86)\RenderDoc\qrenderdoc.exe")),
            ("workspace_renderdoc", Path(r"F:\messiah_official\messiah\Engine\Tools\RenderDoc\qrenderdoc.exe")),
        ]
    )

    seen: set[str] = set()
    rows: list[dict] = []
    for source, candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        norm = str(resolved).lower()
        if norm in seen:
            continue
        seen.add(norm)
        if not resolved.exists():
            continue
        version = detect_renderdoc_version(resolved)
        rows.append(
            {
                "path": str(resolved),
                "version": version,
                "version_tuple": list(parse_version_tuple(version)),
                "source": source,
                "selected": False,
            }
        )

    if not rows:
        raise FileNotFoundError("qrenderdoc.exe not found; use --qrenderdoc-path or install RenderDoc")

    rows.sort(key=lambda row: (tuple(row["version_tuple"]), row["path"].lower()), reverse=True)
    rows[0]["selected"] = True
    chosen = Path(rows[0]["path"])
    return chosen, f"highest_detected_version:{rows[0]['source']}", rows


def build_ui_script(config_b64: str) -> str:
    template = r'''
import base64
import json
import os
import time
import traceback
import renderdoc as rd

CONFIG_B64 = "__CONFIG_B64__"
cfg = json.loads(base64.b64decode(CONFIG_B64.encode("ascii")).decode("utf-8"))

result = {
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "status": "fail",
    "errors": [],
    "capture": {
        "path": cfg.get("rdc_path", ""),
        "api": "",
        "renderdoc_version": cfg.get("renderdoc_version", ""),
        "qrenderdoc_path": cfg.get("qrenderdoc_path", ""),
    },
    "target": {
        "event_id": int(cfg.get("event_id", 0) or 0),
        "output_event_id": int(cfg.get("output_event_id", 0) or 0),
        "output_resource_id": cfg.get("output_resource_id", ""),
        "stage": cfg.get("stage", "pixel"),
        "custom_name": "",
    },
    "shader": {
        "original_resource_id": "",
        "replacement_resource_id": "",
        "post_replace_shader_resource_id": "",
        "replace_target_resource_id": "",
        "mode": "replace_resource",
        "entry_point": cfg.get("entry", "EditedShaderPS"),
        "compile_messages": "",
        "additional_replacements": [],
    },
    "output": {
        "resource_id": "",
        "custom_shader_tex_id": "",
        "display": {},
        "png_path": cfg.get("output_png", ""),
        "json_path": cfg.get("output_json", ""),
        "save_result": "",
        "all_targets": [],
    },
}

def write_result():
    os.makedirs(os.path.dirname(cfg["output_json"]), exist_ok=True)
    with open(cfg["output_json"], "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=2)

def enum_stage(name):
    stage = str(name or "pixel").strip().lower()
    if stage in ("pixel", "ps"):
        return rd.ShaderStage.Pixel
    if stage in ("vertex", "vs"):
        return rd.ShaderStage.Vertex
    if stage in ("compute", "cs"):
        return rd.ShaderStage.Compute
    if stage in ("geometry", "gs"):
        return rd.ShaderStage.Geometry
    if stage in ("hull", "hs", "tess_control"):
        return rd.ShaderStage.Hull
    if stage in ("domain", "ds", "tess_eval"):
        return rd.ShaderStage.Domain
    raise RuntimeError("unsupported shader stage: " + stage)

def valid_output_targets(pipe_state):
    rows = []
    for slot, target in enumerate(list(pipe_state.GetOutputTargets() or [])):
        resource = getattr(target, "resource", rd.ResourceId.Null())
        if resource == rd.ResourceId.Null():
            continue
        rows.append((slot, target, resource))
    return rows

def active_output_target(controller, pipe_state, fallback_targets):
    try:
        tex = controller.GetTextureData(rd.ResourceId.Null(), rd.Subresource(), rd.CompType.Typeless)
    except Exception:
        tex = None
    if tex is not None:
        try:
            rid = getattr(tex, "resourceId", rd.ResourceId.Null())
            if rid != rd.ResourceId.Null():
                for slot, target, resource in fallback_targets:
                    if resource == rid:
                        return slot, target, resource
        except Exception:
            pass
    return fallback_targets[0] if fallback_targets else None

def resolve_texture_resource(controller, requested_resource_id):
    requested = str(requested_resource_id or "").strip()
    if not requested:
        return rd.ResourceId.Null()
    for texture in list(controller.GetTextures() or []):
        resource_id = getattr(texture, "resourceId", rd.ResourceId.Null())
        if str(resource_id) == requested:
            return resource_id
    raise RuntimeError("output texture resource not found: " + requested)

def save_target_png(controller, target, resource_id, png_path):
    save = rd.TextureSave()
    save.resourceId = resource_id
    save.mip = int(getattr(target, "firstMip", 0) or 0)
    save.slice.sliceIndex = int(getattr(target, "firstSlice", 0) or 0)
    save.destType = rd.FileType.PNG
    save.alpha = rd.AlphaMapping.Preserve
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    return controller.SaveTexture(save, png_path)

def save_custom_shader_png(controller, event_id, texture_resource_id, custom_shader, png_path):
    headless = rd.CreateHeadlessWindowingData(1334, 750)
    output = controller.CreateOutput(headless, rd.ReplayOutputType.Texture)
    try:
        controller.SetFrameEvent(event_id, True)
        tex = rd.TextureDisplay()
        tex.resourceId = texture_resource_id
        tex.typeCast = rd.CompType.Typeless
        tex.overlay = rd.DebugOverlay.NoOverlay
        tex.backgroundColor = rd.FloatVector(0.0, 0.0, 0.0, 1.0)
        tex.red = True
        tex.green = True
        tex.blue = True
        tex.alpha = False
        tex.rawOutput = False
        tex.decodeYUV = False
        tex.rangeMin = 0.0
        tex.rangeMax = 1.0
        tex.scale = 1.0
        tex.subresource = rd.Subresource()
        tex.customShaderId = custom_shader
        result["output"]["display"] = {
            "resourceId": str(tex.resourceId),
            "customShaderId": str(tex.customShaderId),
            "rawOutput": bool(tex.rawOutput),
            "decodeYUV": bool(tex.decodeYUV),
            "rangeMin": float(tex.rangeMin),
            "rangeMax": float(tex.rangeMax),
            "scale": float(tex.scale),
            "typeCast": str(tex.typeCast),
        }
        output.SetTextureDisplay(tex)
        output.Display()
        data = output.ReadbackOutputTexture()
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        custom_tex = output.GetCustomShaderTexID()
        try:
            from PIL import Image
            if hasattr(data, "__len__") and len(data) > 0 and isinstance(data[0], int):
                raw = bytes(data)
                pixel_count = 1334 * 750
                if len(raw) == pixel_count * 4:
                    img = Image.frombytes("RGBA", (1334, 750), raw)
                    img.save(png_path)
                    return "<Result: 'Success'>", len(data), str(custom_tex)
                if len(raw) == pixel_count * 3:
                    img = Image.frombytes("RGB", (1334, 750), raw)
                    img.save(png_path)
                    return "<Result: 'Success'>", len(data), str(custom_tex)
        except Exception:
            pass
        save = rd.TextureSave()
        save.resourceId = custom_tex
        save.destType = rd.FileType.PNG
        save.alpha = rd.AlphaMapping.Preserve
        save_result = controller.SaveTexture(save, png_path)
        return save_result, len(data or []), str(custom_tex)
    finally:
        try:
            output.Shutdown()
        except Exception:
            pass

def save_display_png(controller, event_id, texture_resource_id, png_path):
    headless = rd.CreateHeadlessWindowingData(1334, 750)
    output = controller.CreateOutput(headless, rd.ReplayOutputType.Texture)
    try:
        controller.SetFrameEvent(event_id, True)
        tex = rd.TextureDisplay()
        tex.resourceId = texture_resource_id
        tex.typeCast = rd.CompType.Typeless
        tex.overlay = rd.DebugOverlay.NoOverlay
        tex.backgroundColor = rd.FloatVector(0.0, 0.0, 0.0, 1.0)
        tex.red = True
        tex.green = True
        tex.blue = True
        tex.alpha = False
        tex.rawOutput = False
        tex.decodeYUV = False
        tex.rangeMin = 0.0
        tex.rangeMax = 1.0
        tex.scale = 1.0
        tex.subresource = rd.Subresource()
        output.SetTextureDisplay(tex)
        output.Display()
        data = output.ReadbackOutputTexture()
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        try:
            from PIL import Image
            raw = bytes(data)
            pixel_count = 1334 * 750
            if len(raw) == pixel_count * 4:
                Image.frombytes("RGBA", (1334, 750), raw).save(png_path)
                return "<Result: 'Success'>", len(data)
            if len(raw) == pixel_count * 3:
                Image.frombytes("RGB", (1334, 750), raw).save(png_path)
                return "<Result: 'Success'>", len(data)
        except Exception:
            pass
        save = rd.TextureSave()
        save.resourceId = output.GetCustomShaderTexID()
        save.destType = rd.FileType.PNG
        save.alpha = rd.AlphaMapping.Preserve
        save_result = controller.SaveTexture(save, png_path)
        return save_result, len(data or [])
    finally:
        try:
            output.Shutdown()
        except Exception:
            pass

def replay_callback(controller):
    try:
        event_id = int(cfg["event_id"])
        controller.SetFrameEvent(event_id, True)
        pipe_state = controller.GetPipelineState()
        api_props = controller.GetAPIProperties()
        result["capture"]["api"] = str(getattr(api_props, "pipelineType", ""))

        stage_enum = enum_stage(cfg.get("stage", "pixel"))
        original_shader = pipe_state.GetShader(stage_enum)
        replace_target = original_shader
        mode = str(cfg.get("mode", "custom_shader_output") or "custom_shader_output")
        requested_entry = str(cfg.get("entry", "") or "")
        compile_flags = rd.ShaderCompileFlags()
        if mode == "replace_resource":
            reflection = pipe_state.GetShaderReflection(stage_enum)
            entry = requested_entry or str(getattr(reflection, "entryPoint", "") or "")
            debug_info = getattr(reflection, "debugInfo", None)
            if debug_info is not None:
                compile_flags = getattr(debug_info, "compileFlags", compile_flags)
                entry = requested_entry or str(getattr(debug_info, "entrySourceName", "") or entry)
        else:
            entry = requested_entry or "EditedShaderPS"
        if not entry:
            entry = "main"
        result["shader"]["original_resource_id"] = str(original_shader)
        result["shader"]["entry_point"] = entry
        result["shader"]["compile_flags"] = [
            {"name": str(flag.name), "value": str(flag.value)}
            for flag in getattr(compile_flags, "flags", [])
        ]

        with open(cfg["shader_path"], "rb") as fp:
            source = fp.read()
        build_func = controller.BuildTargetShader if mode == "replace_resource" else controller.BuildCustomShader
        replacement, messages = build_func(
            entry,
            rd.ShaderEncoding.HLSL,
            source,
            compile_flags,
            stage_enum,
        )
        result["shader"]["replacement_resource_id"] = str(replacement)
        result["shader"]["compile_messages"] = str(messages or "")
        if replacement == rd.ResourceId.Null():
            raise RuntimeError("BuildTargetShader failed: " + str(messages))

        result["shader"]["mode"] = mode
        targets = valid_output_targets(pipe_state)
        requested_output_resource = str(cfg.get("output_resource_id", "") or "").strip()
        if not targets and not requested_output_resource:
            raise RuntimeError("no valid output render target at event")
        chosen = active_output_target(controller, pipe_state, targets)
        if chosen is None and not requested_output_resource:
            raise RuntimeError("no active output render target resolved at event")
        if chosen is not None:
            slot0, target0, target_resource0 = chosen
            result["output"]["resource_id"] = str(target_resource0)
            result["output"]["selected_slot"] = int(slot0)
        else:
            slot0, target0, target_resource0 = -1, None, rd.ResourceId.Null()

        output_base, output_ext = os.path.splitext(cfg["output_png"])
        all_rows = []
        try:
            if mode == "replace_resource":
                result["shader"]["replace_target_resource_id"] = str(replace_target)
                controller.ReplaceResource(replace_target, replacement)
                replaced_resource_ids = {str(replace_target)}
                for additional_event_id in list(cfg.get("additional_event_ids", []) or []):
                    controller.SetFrameEvent(int(additional_event_id), True)
                    additional_pipeline = controller.GetPipelineState()
                    additional_original = additional_pipeline.GetShader(stage_enum)
                    if additional_original == rd.ResourceId.Null() or str(additional_original) in replaced_resource_ids:
                        continue
                    additional_reflection = additional_pipeline.GetShaderReflection(stage_enum)
                    additional_debug_info = getattr(additional_reflection, "debugInfo", None)
                    additional_flags = getattr(additional_debug_info, "compileFlags", rd.ShaderCompileFlags())
                    additional_entry = requested_entry or str(getattr(additional_debug_info, "entrySourceName", "") or getattr(additional_reflection, "entryPoint", "") or entry)
                    additional_replacement, additional_messages = controller.BuildTargetShader(
                        additional_entry,
                        rd.ShaderEncoding.HLSL,
                        source,
                        additional_flags,
                        stage_enum,
                    )
                    if additional_replacement == rd.ResourceId.Null():
                        raise RuntimeError("BuildTargetShader failed for additional event " + str(additional_event_id) + ": " + str(additional_messages))
                    controller.ReplaceResource(additional_original, additional_replacement)
                    replaced_resource_ids.add(str(additional_original))
                    result["shader"]["additional_replacements"].append({
                        "event_id": int(additional_event_id),
                        "original_resource_id": str(additional_original),
                        "replacement_resource_id": str(additional_replacement),
                        "entry_point": additional_entry,
                        "compile_messages": str(additional_messages or ""),
                    })
                output_event_id = int(cfg.get("output_event_id", 0) or event_id)
                controller.SetFrameEvent(output_event_id, True)
                requested_output_resource = str(cfg.get("output_resource_id", "") or "").strip()
                if requested_output_resource:
                    target_resource0 = resolve_texture_resource(controller, requested_output_resource)
                    targets = []
                    result["output"]["resource_id"] = str(target_resource0)
                    result["output"]["selected_slot"] = -1
                elif output_event_id != event_id:
                    output_pipe_state = controller.GetPipelineState()
                    targets = valid_output_targets(output_pipe_state)
                    if not targets:
                        raise RuntimeError("no valid output render target at output event")
                    chosen = active_output_target(controller, output_pipe_state, targets)
                    if chosen is None:
                        raise RuntimeError("no active output render target resolved at output event")
                    slot0, target0, target_resource0 = chosen
                    result["output"]["resource_id"] = str(target_resource0)
                    result["output"]["selected_slot"] = int(slot0)
                result["output"]["event_id"] = output_event_id
                save_result, display_readback_len = save_display_png(
                    controller, output_event_id, target_resource0, cfg["output_png"]
                )
                result["output"]["save_result"] = str(save_result)
                result["output"]["readback_len"] = int(display_readback_len)
                for slot, target, resource_id in targets:
                    slot_png = f"{output_base}.slot{slot}{output_ext}"
                    slot_save_result, slot_readback_len = save_display_png(
                        controller, output_event_id, resource_id, slot_png
                    )
                    all_rows.append(
                        {
                            "slot": int(slot),
                            "resource_id": str(resource_id),
                            "first_mip": int(getattr(target, "firstMip", 0) or 0),
                            "first_slice": int(getattr(target, "firstSlice", 0) or 0),
                            "png_path": slot_png,
                            "save_result": str(slot_save_result),
                            "readback_len": int(slot_readback_len),
                            "custom_shader_tex_id": "",
                        }
                    )
            else:
                save_result, readback_len, custom_tex_id = save_custom_shader_png(
                    controller, event_id, target_resource0, replacement, cfg["output_png"]
                )
                result["output"]["save_result"] = str(save_result)
                result["output"]["readback_len"] = int(readback_len)
                result["output"]["custom_shader_tex_id"] = str(custom_tex_id)
                for slot, target, resource_id in targets:
                    slot_png = f"{output_base}.slot{slot}{output_ext}"
                    slot_save_result, slot_readback_len, slot_custom_tex_id = save_custom_shader_png(
                        controller, event_id, resource_id, replacement, slot_png
                    )
                    all_rows.append(
                        {
                            "slot": int(slot),
                            "resource_id": str(resource_id),
                            "first_mip": int(getattr(target, "firstMip", 0) or 0),
                            "first_slice": int(getattr(target, "firstSlice", 0) or 0),
                            "png_path": slot_png,
                            "save_result": str(slot_save_result),
                            "readback_len": int(slot_readback_len),
                            "custom_shader_tex_id": str(slot_custom_tex_id),
                        }
                    )
        finally:
            if mode == "replace_resource":
                try:
                    controller.RemoveReplacement(replace_target)
                except Exception:
                    pass
                controller.FreeTargetResource(replacement)
            else:
                controller.FreeCustomShader(replacement)
        if mode == "replace_resource":
                result["shader"]["post_replace_shader_resource_id"] = str(
                    controller.GetPipelineState().GetShader(stage_enum)
                )
        result["output"]["all_targets"] = all_rows

        result["status"] = "success"
    except Exception as exc:
        result["errors"].append(repr(exc))
        result["errors"].append(traceback.format_exc())
    finally:
        write_result()

try:
    pyrenderdoc.Replay().BlockInvoke(replay_callback)
except Exception as exc:
    result["errors"].append("BlockInvoke failed: " + repr(exc))
    result["errors"].append(traceback.format_exc())
    write_result()
'''
    return textwrap.dedent(template).replace("__CONFIG_B64__", config_b64)


def png_stats(path: Path) -> dict:
    try:
        from PIL import Image
    except Exception as exc:
        return {"available": False, "reason": f"pillow_unavailable:{exc!r}"}
    if not path.exists():
        return {"available": False, "reason": "png_missing"}
    with Image.open(path) as img:
        rgba = img.convert("RGBA")
        width, height = rgba.size
        hist = rgba.histogram()
        pixels = width * height
        means = []
        for channel in range(4):
            base = channel * 256
            total = sum(value * hist[base + value] for value in range(256))
            means.append(total / max(1, pixels) / 255.0)
        red_dominant = green_dominant = blue_dominant = black = white = 0
        sample_step = max(1, int((pixels / 250000) ** 0.5))
        for y in range(0, height, sample_step):
            for x in range(0, width, sample_step):
                r, g, b, a = rgba.getpixel((x, y))
                if r < 16 and g < 16 and b < 16:
                    black += 1
                if r > 240 and g > 240 and b > 240:
                    white += 1
                if r > g + 32 and r > b + 32:
                    red_dominant += 1
                elif g > r + 32 and g > b + 32:
                    green_dominant += 1
                elif b > r + 32 and b > g + 32:
                    blue_dominant += 1
        sampled = len(range(0, height, sample_step)) * len(range(0, width, sample_step))
        return {
            "available": True,
            "width": width,
            "height": height,
            "mean_rgba": means,
            "sample_step": sample_step,
            "sampled_pixels": sampled,
            "dominance_ratio": {
                "red": red_dominant / max(1, sampled),
                "green": green_dominant / max(1, sampled),
                "blue": blue_dominant / max(1, sampled),
                "black": black / max(1, sampled),
                "white": white / max(1, sampled),
            },
        }


def collect_slot_png_stats(payload: dict) -> None:
    output = payload.get("output", {})
    rows = output.get("all_targets", []) or []
    for row in rows:
        png_path = row.get("png_path", "")
        row["png_stats"] = png_stats(Path(png_path)) if png_path else {"available": False, "reason": "png_path_missing"}


def is_json_ready(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a RenderDoc shader replacement and export a debug PNG.")
    parser.add_argument("--rdc-path", required=True)
    parser.add_argument("--event-id", required=True, type=int)
    parser.add_argument("--output-event-id", type=int, default=0)
    parser.add_argument("--output-resource-id", default="")
    parser.add_argument("--additional-event-id", action="append", type=int, default=[])
    parser.add_argument("--shader-path", required=True)
    parser.add_argument("--output-png", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--stage", default="pixel")
    parser.add_argument("--entry", default="")
    parser.add_argument("--mode", choices=("custom_shader_output", "replace_resource"), default="custom_shader_output")
    parser.add_argument("--qrenderdoc-path", default="")
    parser.add_argument("--timeout-sec", type=float, default=120.0)
    args = parser.parse_args()

    rdc_path = Path(args.rdc_path).resolve()
    shader_path = Path(args.shader_path).resolve()
    output_png = Path(args.output_png).resolve()
    output_json = Path(args.output_json).resolve()
    if not rdc_path.exists():
        raise FileNotFoundError(rdc_path)
    if not shader_path.exists():
        raise FileNotFoundError(shader_path)

    qrenderdoc_path, qrenderdoc_selection_reason, qrenderdoc_candidates = detect_qrenderdoc(args.qrenderdoc_path)
    renderdoc_version = detect_renderdoc_version(qrenderdoc_path)
    for stale_path in (output_json, output_png):
        try:
            stale_path.unlink(missing_ok=True)
        except Exception:
            pass
    cfg = {
        "rdc_path": str(rdc_path),
        "event_id": int(args.event_id),
        "output_event_id": int(args.output_event_id),
        "output_resource_id": args.output_resource_id,
        "additional_event_ids": args.additional_event_id,
        "shader_path": str(shader_path),
        "output_png": str(output_png),
        "output_json": str(output_json),
        "stage": args.stage,
        "entry": args.entry,
        "mode": args.mode,
        "qrenderdoc_path": str(qrenderdoc_path),
        "renderdoc_version": renderdoc_version,
        "qrenderdoc_selection_reason": qrenderdoc_selection_reason,
        "qrenderdoc_candidates": qrenderdoc_candidates,
    }
    cfg_b64 = base64.b64encode(json.dumps(cfg, ensure_ascii=False).encode("utf-8")).decode("ascii")
    script_text = build_ui_script(cfg_b64)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as fp:
        ui_script = Path(fp.name)
        fp.write(script_text)

    started_at = time.time()
    proc: subprocess.Popen | None = None
    stdout_text = ""
    stderr_text = ""
    timed_out = False
    try:
        proc = subprocess.Popen(
            [str(qrenderdoc_path), "--ui-python", str(ui_script), str(rdc_path)],
            cwd=str(rdc_path.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = started_at + max(1.0, float(args.timeout_sec))
        while time.time() < deadline:
            if is_json_ready(output_json) and output_png.exists():
                break
            if proc.poll() is not None:
                break
            time.sleep(0.25)

        if proc.poll() is None:
            if is_json_ready(output_json) and output_png.exists():
                proc.terminate()
            else:
                timed_out = True
                proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()

        try:
            stdout_text, stderr_text = proc.communicate(timeout=5)
        except Exception:
            stdout_text, stderr_text = "", ""
    except Exception as exc:
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "fail",
            "errors": [f"qrenderdoc_launch_failed:{exc!r}"],
            "runner": {"ui_script": str(ui_script), "duration_sec": round(time.time() - started_at, 3)},
        }
        write_json(output_json, payload)
        return 2
    finally:
        try:
            ui_script.unlink(missing_ok=True)
        except Exception:
            pass

    if not output_json.exists():
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "fail",
            "errors": ["output_json_missing_after_qrenderdoc"] + (["qrenderdoc_timeout"] if timed_out else []),
            "runner": {
                "returncode": proc.returncode if proc else None,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "duration_sec": round(time.time() - started_at, 3),
            },
        }
        write_json(output_json, payload)
        return 124 if timed_out else 2

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    payload["runner"] = {
        "returncode": proc.returncode if proc else None,
        "stdout_tail": (stdout_text or "")[-4000:],
        "stderr_tail": (stderr_text or "")[-4000:],
        "duration_sec": round(time.time() - started_at, 3),
        "terminated_after_output": bool(not timed_out and output_png.exists()),
        "timed_out": bool(timed_out),
        "qrenderdoc_path": str(qrenderdoc_path),
        "renderdoc_version": renderdoc_version,
        "qrenderdoc_selection_reason": qrenderdoc_selection_reason,
        "qrenderdoc_candidates": qrenderdoc_candidates,
    }
    payload["png_stats"] = png_stats(output_png)
    collect_slot_png_stats(payload)
    write_json(output_json, payload)
    return 0 if payload.get("status") == "success" and output_png.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
