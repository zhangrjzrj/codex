---
name: "image-payload-optimizer"
description: "Create lightweight preview images before Codex inspects large screenshots or raster evidence to reduce multimodal payload. Use for GUI feedback loops, macOS/Windows/ADB/Playwright screenshots, large PNG/JPG/WebP files, or repeated visual evidence review. Do not use to rewrite screenshots that are part of coordinate-mapped automation unless the original scale metadata is preserved and the preview is only for visual inspection."
---

# Image Payload Optimizer

Use this skill when an image or screenshot is likely to inflate request payload, especially before `view_image` on large GUI screenshots.

## Rule

Preserve the original image as evidence. Generate a smaller preview for model inspection. Treat the preview as read-only visual evidence unless coordinate metadata explicitly says otherwise.

Default trigger:
- File size is greater than 1 MB.
- Either image edge is greater than 1600 px.
- A workflow repeatedly captures screenshots.
- The screenshot comes from macOS `screencapture`, Windows desktop capture, ADB, Playwright/CDP, browser automation, or GUI test evidence.

Default preview target:
- Max edge: 1280 px.
- JPEG or WebP when alpha is not needed.
- PNG only when transparency or exact UI edges are important.
- Quality: 70-80 for JPEG/WebP.

## Coordinate Safety

1. Do not second-compress screenshots used for coordinate back-mapping.
2. If an MCP or automation channel already outputs a compressed image plus scale metadata, use that image and its mapping metadata directly.
3. Use this skill only for visual inspection, evidence preview, and payload reduction.
4. If a preview may later inform clicks or coordinate math, record original width/height, preview width/height, and scale ratios.
5. Always keep the original image. The optimized file is a preview, not the source of truth.

Examples of coordinate-mapped channels:
- CDP MCP screenshot with scale metadata used to convert preview clicks back to page coordinates.
- ADB screenshot used for tap coordinate derivation.
- UIA or desktop automation screenshot used to compute mouse coordinates.
- Playwright screenshot tied to browser viewport coordinates.

When in doubt, do not replace the screenshot in the automation path. Create a sibling preview named like `<name>.preview.jpg` and clearly label it as visual-only.

## Workflow

1. Check image size and purpose before viewing.
2. If the image is small or already optimized, inspect it directly.
3. If it is large and not coordinate-sensitive, generate a preview and inspect the preview.
4. If it is coordinate-sensitive, inspect existing channel metadata first. Only generate an extra visual-only preview if needed.
5. Report which file was viewed and whether it is original or preview.

## Tools

Preferred helper:

```powershell
python "$env:CODEX_HOME\skills\image-payload-optimizer\scripts\make_preview.py" <input-image> --out <preview-image>
```

When `CODEX_HOME` is unset, use the absolute skill path under `~/.codex/skills/image-payload-optimizer/scripts/make_preview.py`.

macOS fallback over SSH:

```bash
sips -Z 1280 input.png --out preview.png
```

ImageMagick fallback:

```bash
magick input.png -auto-orient -resize '1280x1280>' -quality 78 preview.jpg
```

## Output Discipline

- Put previews in the project's ignored evidence/tmp directory when one exists.
- Do not scatter previews into repository roots.
- Name previews predictably: `original-name.preview.jpg`, `original-name.preview.png`, or `original-name.preview.webp`.
- Do not delete originals unless the user explicitly asks.
- Do not commit previews unless the user explicitly wants evidence files versioned.
