---
name: "procedural-alpha-fx"
description: "Generate and iterate transparent RGBA visual effects with Python/Pillow, such as lightning, rain, snow, sparks, fog, scanlines, glows, or energy overlays, when deterministic alpha assets are preferable to AI video or manual art."
---

# Procedural Alpha Fx

Use this skill when a task needs a reusable transparent visual effect that can be drawn procedurally, inspected, tuned, and exported as an image sequence, video, or engine-ready asset.

## Fit

Prefer this workflow for effects whose look is mostly geometric, temporal, or parametric:

- Lightning, rain, snow, sparks, embers, scanning lines, magic/energy strokes, glints, soft fog, vignette flashes, screen overlays.
- Looping or flickering assets where timing, alpha, and placement matter more than cinematic world understanding.
- Cases where deterministic output, clean transparency, small file size, or closed-loop tuning is more valuable than prompt-based novelty.

Do not use this as the first choice for complex natural simulations or cinematic footage such as realistic explosions, volumetric cloud evolution, smoke plumes, or fluid dynamics unless a stylized/procedural result is acceptable.

## Workflow

1. Create generated frames in an ignored evidence or artifact directory, not the repo root.
2. Use Python with Pillow to generate `RGBA` frames on a transparent background.
3. Fix the random seed when visual repeatability matters.
4. Generate a few representative preview frames first; inspect them before rendering the full sequence.
5. Tune parameters from visual evidence: position, alpha, glow radius, density, speed, stroke width, frame cadence, and loop length.
6. Export the approved sequence as PNG frames. If a video intermediate is needed, use `ffmpeg` with ProRes 4444 and an alpha pixel format such as `yuva444p10le`.
7. Validate alpha and motion before integrating: alpha min/max, partial-alpha presence, frame count, frame rate, file size, and at least one visual screenshot.
8. If the target runtime uses a custom asset format, encode only after previews are acceptable, then verify in the actual runtime.

## Practical Rules

- Keep source generation scripts with evidence unless the user asks for a reusable project script.
- Treat ignored evidence outputs as temporary unless the user asks to commit generated assets.
- For project-referenced assets, copy the final artifact into a tracked asset path or clearly report if the path is ignored and requires force-add.
- Avoid tool identity strings in generated business paths, filenames, logs, status labels, and asset names.
- If an output is used in a browser or game runtime, update cache-busting version strings after replacing assets.

## Effect Notes

- **Lightning:** Draw a main jagged polyline, add branches, then composite several blurred glow layers under a thin white core. Place it against darker scenery; bright sky or sun bloom can hide it. Use burst/afterglow timing rather than uniform visibility.
- **Rain:** Prefer a lower-resolution full-screen or camera-attached alpha layer for dense rain. Excessively fine high-resolution streaks can make encoding slow and increase runtime cost. Mix distant rain curtain, near streaks, and subtle bottom haze.
- **Flicker:** Encode flicker explicitly in the frame sequence. A strong frame followed by two to six decaying frames usually reads better than random every-frame noise.
- **Looping:** Make the first and last frames visually compatible or use procedural wraparound so repeated playback does not pop.
- **Alpha:** Keep RGB meaningful only where alpha is nonzero. Inspect transparent edges because unwanted low-alpha rectangles are visible in additive or transparent compositing.

## Verification

Minimum useful evidence:

- One preview frame for each important visual state.
- Runtime screenshot after integration.
- Output metadata: resolution, frame count, frame rate, alpha format or alpha range.
- If animated motion matters, compare two frames or screenshots from different times.

For NBS-style pipelines:

- Generate RGBA PNG frames.
- Convert to ProRes 4444 MOV with `ffmpeg`.
- Encode with the local NewBasis encoder only after the MOV is confirmed to preserve alpha.
- Verify decoder/runtime status shows advancing frames, nonzero FPS, alpha range, and the expected visible/hidden behavior.
