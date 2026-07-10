#!/usr/bin/env python3
"""Create a lightweight preview image while preserving the original."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a low-payload preview image.")
    parser.add_argument("input", help="Source image path")
    parser.add_argument("--out", help="Preview output path")
    parser.add_argument("--max-edge", type=int, default=1280, help="Maximum preview edge in pixels")
    parser.add_argument("--quality", type=int, default=78, help="JPEG/WebP quality")
    parser.add_argument(
        "--format",
        choices=["auto", "jpg", "jpeg", "png", "webp"],
        default="auto",
        help="Preview output format",
    )
    parser.add_argument(
        "--metadata",
        help="Optional JSON path for original/preview dimensions and scale ratios",
    )
    return parser.parse_args()


def load_pillow():
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise SystemExit(
            "Pillow is required for make_preview.py. Install pillow or use sips/ImageMagick fallback."
        ) from exc
    return Image, ImageOps


def choose_output(input_path: Path, output_arg: str | None, fmt: str) -> tuple[Path, str]:
    if fmt == "jpeg":
        fmt = "jpg"
    if output_arg:
        output_path = Path(output_arg)
        suffix = output_path.suffix.lower().lstrip(".")
        if fmt == "auto":
            fmt = "jpg" if suffix in {"jpg", "jpeg"} else suffix or "jpg"
        return output_path, fmt

    if fmt == "auto":
        fmt = "jpg"
    output_path = input_path.with_name(f"{input_path.stem}.preview.{fmt}")
    return output_path, fmt


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path, fmt = choose_output(input_path, args.out, args.format)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    Image, ImageOps = load_pillow()
    with Image.open(input_path) as image:
        image = ImageOps.exif_transpose(image)
        original_size = image.size
        preview = image.copy()
        preview.thumbnail((args.max_edge, args.max_edge), Image.Resampling.LANCZOS)

        save_kwargs = {}
        if fmt in {"jpg", "jpeg"}:
            if preview.mode in {"RGBA", "LA", "P"}:
                preview = preview.convert("RGB")
            save_format = "JPEG"
            save_kwargs.update({"quality": args.quality, "optimize": True, "progressive": True})
        elif fmt == "webp":
            save_format = "WEBP"
            save_kwargs.update({"quality": args.quality, "method": 6})
        elif fmt == "png":
            save_format = "PNG"
            save_kwargs.update({"optimize": True})
        else:
            raise SystemExit(f"Unsupported output format: {fmt}")

        preview.save(output_path, save_format, **save_kwargs)
        preview_size = preview.size

    metadata = {
        "source": str(input_path),
        "preview": str(output_path),
        "original_width": original_size[0],
        "original_height": original_size[1],
        "preview_width": preview_size[0],
        "preview_height": preview_size[1],
        "scale_x": preview_size[0] / original_size[0] if original_size[0] else None,
        "scale_y": preview_size[1] / original_size[1] if original_size[1] else None,
        "visual_only": True,
    }
    if args.metadata:
        metadata_path = Path(args.metadata)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(metadata, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
