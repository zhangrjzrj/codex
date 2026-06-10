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


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_qrenderdoc(requested_path: str) -> Path:
    candidates: list[Path] = []
    if requested_path and requested_path.strip():
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
    raise FileNotFoundError("qrenderdoc.exe not found; use --qrenderdoc-path or RENDERDOC_QRENDERDOC")


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
        "stage": cfg.get("stage", "pixel"),
        "custom_name": "",
    },
    "shader": {
        "original_resource_id": "",
        "replacement_resource_id": "",
        "entry_point": cfg.get("entry", "EditedShaderPS"),
        "compile_messages": "",
    },
    "output": {
        "resource_id": "",
        "png_path": cfg.get("output_png", ""),
        "json_path": cfg.get("output_json", ""),
        "save_result": "",
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

def first_valid_output_target(pipe_state):
    for target in list(pipe_state.GetOutputTargets() or []):
        resource = getattr(target, "resource", rd.ResourceId.Null())
        if resource != rd.ResourceId.Null():
            return target, resource
    return None, rd.ResourceId.Null()

def replay_callback(controller):
    try:
        event_id = int(cfg["event_id"])
        controller.SetFrameEvent(event_id, True)
        pipe_state = controller.GetPipelineState()
        api_props = controller.GetAPIProperties()
        result["capture"]["api"] = str(getattr(api_props, "pipelineType", ""))

        stage_enum = enum_stage(cfg.get("stage", "pixel"))
        original_shader = pipe_state.GetShader(stage_enum)
        entry = str(cfg.get("entry", "EditedShaderPS") or "EditedShaderPS")
        result["shader"]["original_resource_id"] = str(original_shader)
        result["shader"]["entry_point"] = entry

        with open(cfg["shader_path"], "rb") as fp:
            source = fp.read()
        replacement, messages = controller.BuildTargetShader(
            entry,
            rd.ShaderEncoding.HLSL,
            source,
            rd.ShaderCompileFlags(),
            stage_enum,
        )
        result["shader"]["replacement_resource_id"] = str(replacement)
        result["shader"]["compile_messages"] = str(messages or "")
        if replacement == rd.ResourceId.Null():
            raise RuntimeError("BuildTargetShader failed: " + str(messages))

        controller.ReplaceResource(original_shader, replacement)
        controller.SetFrameEvent(event_id, True)
        pipe_state = controller.GetPipelineState()
        target, target_resource = first_valid_output_target(pipe_state)
        result["output"]["resource_id"] = str(target_resource)
        if target_resource == rd.ResourceId.Null():
            raise RuntimeError("no valid output render target at event")

        save = rd.TextureSave()
        save.resourceId = target_resource
        save.mip = int(getattr(target, "firstMip", 0) or 0)
        save.slice.sliceIndex = int(getattr(target, "firstSlice", 0) or 0)
        save.destType = rd.FileType.PNG
        save.alpha = rd.AlphaMapping.Preserve
        os.makedirs(os.path.dirname(cfg["output_png"]), exist_ok=True)
        save_result = controller.SaveTexture(save, cfg["output_png"])
        result["output"]["save_result"] = str(save_result)

        controller.RemoveReplacement(original_shader)
        controller.FreeTargetResource(replacement)
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
    parser.add_argument("--shader-path", required=True)
    parser.add_argument("--output-png", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--stage", default="pixel")
    parser.add_argument("--entry", default="EditedShaderPS")
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

    qrenderdoc_path = detect_qrenderdoc(args.qrenderdoc_path)
    renderdoc_version = detect_renderdoc_version(qrenderdoc_path)
    for stale_path in (output_json, output_png):
        try:
            stale_path.unlink(missing_ok=True)
        except Exception:
            pass
    cfg = {
        "rdc_path": str(rdc_path),
        "event_id": int(args.event_id),
        "shader_path": str(shader_path),
        "output_png": str(output_png),
        "output_json": str(output_json),
        "stage": args.stage,
        "entry": args.entry,
        "qrenderdoc_path": str(qrenderdoc_path),
        "renderdoc_version": renderdoc_version,
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
    }
    payload["png_stats"] = png_stats(output_png)
    write_json(output_json, payload)
    return 0 if payload.get("status") == "success" and output_png.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
