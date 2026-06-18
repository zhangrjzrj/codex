#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a non-minimized RenderDoc window via PrintWindow.")
    parser.add_argument("--window-title", required=True, help="Substring to match the RenderDoc window title.")
    parser.add_argument("--output-png", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    output_png = Path(args.output_png).resolve()
    output_json = Path(args.output_json).resolve()

    result = {
        "status": "fail",
        "errors": [],
        "window_title_query": args.window_title,
        "matched_window_title": "",
        "matched_window_handle": 0,
        "width": 0,
        "height": 0,
        "printwindow_result": 0,
        "getdibits_rows": 0,
        "output_png": str(output_png),
    }

    try:
        import ctypes
        from ctypes import wintypes
        from pywinauto import Desktop
        from PIL import Image
    except Exception as exc:
        result["errors"].append(f"import_failed:{exc!r}")
        write_json(output_json, result)
        return 2

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    PW_RENDERFULLCONTENT = 0x00000002

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    try:
        windows = [
            w
            for w in Desktop(backend="uia").windows()
            if args.window_title in (w.window_text() or "")
        ]
        if not windows:
            raise RuntimeError(f"target_window_not_found:{args.window_title}")

        target = windows[0]
        handle = int(target.handle)
        result["matched_window_title"] = target.window_text()
        result["matched_window_handle"] = handle

        rect = RECT()
        if user32.GetWindowRect(handle, ctypes.byref(rect)) == 0:
            raise RuntimeError("GetWindowRect failed")

        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width <= 0 or height <= 0:
            raise RuntimeError(f"invalid_window_size:{width}x{height}")

        result["width"] = width
        result["height"] = height

        hwnd_dc = user32.GetWindowDC(handle)
        mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
        bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
        gdi32.SelectObject(mem_dc, bitmap)

        try:
            result["printwindow_result"] = int(user32.PrintWindow(handle, mem_dc, PW_RENDERFULLCONTENT))

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = width
            bmi.biHeight = -height
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0

            buf_len = width * height * 4
            buffer = ctypes.create_string_buffer(buf_len)
            rows = gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(bmi), 0)
            result["getdibits_rows"] = int(rows)

            output_png.parent.mkdir(parents=True, exist_ok=True)
            image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)
            image.save(output_png)
        finally:
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(handle, hwnd_dc)

        result["status"] = "success"
        write_json(output_json, result)
        return 0
    except Exception as exc:
        result["errors"].append(repr(exc))
        write_json(output_json, result)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
