import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def parse_csv(value, expected_count, label):
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != expected_count:
        raise ValueError(f"{label} requires {expected_count} comma-separated values")
    return parts


def resolve_roi(args, width, height):
    if args.roi:
        x, y, roi_width, roi_height = [int(value) for value in parse_csv(args.roi, 4, "--roi")]
        box = (x, y, x + roi_width, y + roi_height)
    elif args.roi_fraction:
        left, top, right, bottom = parse_csv(args.roi_fraction, 4, "--roi-fraction")
        if not all(0.0 <= value <= 1.0 for value in (left, top, right, bottom)):
            raise ValueError("--roi-fraction values must be between 0 and 1")
        box = (
            int(round(left * width)),
            int(round(top * height)),
            int(round(right * width)),
            int(round(bottom * height)),
        )
    else:
        box = (0, 0, width, height)
    left, top, right, bottom = box
    if left < 0 or top < 0 or right > width or bottom > height or right <= left or bottom <= top:
        raise ValueError(f"ROI is outside the frame: {box} for {width}x{height}")
    return box


def heat_color(values):
    values = np.clip(values, 0.0, 1.0)
    red = np.clip(values * 3.0, 0.0, 1.0)
    green = np.clip((values - 0.25) * 2.0, 0.0, 1.0)
    blue = np.clip((values - 0.65) * 3.0, 0.0, 1.0)
    return np.stack([red, green, blue], axis=2)


def make_contact_sheet(images, output_path):
    indices = sorted(set([0, len(images) // 4, len(images) // 2, (len(images) * 3) // 4, len(images) - 1]))
    selected = [images[index] for index in indices]
    thumb_width = 320
    thumbs = []
    for image in selected:
        ratio = thumb_width / image.width
        thumbs.append(image.resize((thumb_width, max(1, int(image.height * ratio))), Image.Resampling.LANCZOS))
    sheet = Image.new("RGB", (thumb_width * len(thumbs), max(thumb.height for thumb in thumbs)), "black")
    draw = ImageDraw.Draw(sheet)
    for column, (index, thumb) in enumerate(zip(indices, thumbs)):
        x = column * thumb_width
        sheet.paste(thumb, (x, 0))
        draw.text((x + 6, 6), f"frame {index}", fill="white")
    sheet.save(output_path)


def main():
    parser = argparse.ArgumentParser(description="Analyze temporal changes in a window-capture PNG sequence")
    parser.add_argument("--frames-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--roi")
    parser.add_argument("--roi-fraction")
    parser.add_argument("--baseline-report")
    parser.add_argument("--max-baseline-ratio", type=float, default=1.25)
    parser.add_argument("--pixel-threshold", type=float, default=0.02)
    args = parser.parse_args()

    frames_dir = Path(args.frames_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_paths = sorted(frames_dir.glob("frame_*.png"))
    if not frame_paths:
        frame_paths = sorted(frames_dir.glob("frame_*.bmp"))
    if len(frame_paths) < 2:
        raise ValueError("At least two frame PNG or BMP files are required")

    first = Image.open(frame_paths[0]).convert("RGB")
    width, height = first.size
    roi = resolve_roi(args, width, height)
    pil_frames = []
    arrays = []
    for path in frame_paths:
        image = Image.open(path).convert("RGB")
        if image.size != (width, height):
            raise ValueError(f"Frame size changed at {path}: {image.size} != {(width, height)}")
        cropped = image.crop(roi)
        pil_frames.append(cropped)
        arrays.append(np.asarray(cropped, dtype=np.float32) / 255.0)

    stack = np.stack(arrays, axis=0)
    differences = np.abs(np.diff(stack, axis=0))
    difference_luma = differences.mean(axis=3)
    per_pair_mean = difference_luma.mean(axis=(1, 2))
    per_pair_changed_ratio = (difference_luma > args.pixel_threshold).mean(axis=(1, 2))
    temporal_mean = difference_luma.mean(axis=0)
    temporal_p95 = np.percentile(difference_luma, 95, axis=0)
    energy = float(per_pair_mean.mean())
    changed_ratio = float(per_pair_changed_ratio.mean())

    normalization = max(float(np.percentile(temporal_p95, 99.5)), 1e-6)
    heat = heat_color(temporal_p95 / normalization)
    Image.fromarray((heat * 255.0).astype(np.uint8), "RGB").save(output_dir / "temporal_heatmap.png")
    Image.fromarray((np.clip(temporal_mean / normalization, 0.0, 1.0) * 255.0).astype(np.uint8), "L").save(
        output_dir / "temporal_mean.png"
    )
    make_contact_sheet(pil_frames, output_dir / "contact_sheet.png")

    baseline_energy = None
    baseline_ratio = None
    passed = None
    if args.baseline_report:
        baseline = json.loads(Path(args.baseline_report).read_text(encoding="utf-8-sig"))
        baseline_energy = float(baseline["metrics"]["mean_frame_difference"])
        baseline_ratio = energy / max(baseline_energy, 1e-9)
        passed = baseline_ratio <= args.max_baseline_ratio

    report = {
        "status": "pass" if passed is True else "fail" if passed is False else "measured",
        "frames": {
            "directory": str(frames_dir.resolve()),
            "count": len(frame_paths),
            "width": width,
            "height": height,
        },
        "roi": {
            "left": roi[0],
            "top": roi[1],
            "right": roi[2],
            "bottom": roi[3],
            "width": roi[2] - roi[0],
            "height": roi[3] - roi[1],
        },
        "metrics": {
            "mean_frame_difference": energy,
            "mean_changed_pixel_ratio": changed_ratio,
            "pixel_threshold": args.pixel_threshold,
            "pair_mean_min": float(per_pair_mean.min()),
            "pair_mean_max": float(per_pair_mean.max()),
            "pair_mean_p95": float(np.percentile(per_pair_mean, 95)),
        },
        "baseline": {
            "report": str(Path(args.baseline_report).resolve()) if args.baseline_report else None,
            "mean_frame_difference": baseline_energy,
            "ratio": baseline_ratio,
            "max_ratio": args.max_baseline_ratio if args.baseline_report else None,
        },
        "artifacts": {
            "heatmap": str((output_dir / "temporal_heatmap.png").resolve()),
            "temporal_mean": str((output_dir / "temporal_mean.png").resolve()),
            "contact_sheet": str((output_dir / "contact_sheet.png").resolve()),
        },
    }
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
