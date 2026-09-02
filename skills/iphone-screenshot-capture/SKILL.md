---
name: "iphone-screenshot-capture"
description: "Capture a real iPhone or iPad screen through a remote Mac using pymobiledevice3 DVT, validate the PNG, and copy it to a local evidence path. Use when device-visible screenshot evidence is needed without ADB, simulator capture, or manual screenshots."
---

# iPhone Screenshot Capture

Capture the current physical iOS device screen through an SSH-accessible Mac.

## Workflow

1. Confirm the Mac SSH alias works and the target device is `connected` in `xcrun devicectl list devices`.
2. Run `scripts/capture_iphone_screenshot.py` locally. It invokes `pymobiledevice3 developer dvt screenshot --userspace` on the Mac and copies the result back with SCP.
3. Require a nonempty PNG with valid dimensions before reporting success.
4. Return the local absolute path. Keep evidence in the project's ignored evidence directory when one exists.

## Command

```powershell
python scripts/capture_iphone_screenshot.py `
  --ssh-host mac-h74 `
  --udid 00008110-001A5C1226B8401E `
  --output F:\project\.j-evidence\iphone.png
```

Optional `--python` selects the remote Python executable. The default is Xcode's bundled Python, which is the verified Messiah Mac setup.

## Boundaries

- This skill only captures and validates the visible device screen.
- It does not launch, foreground, tap, unlock, install, or modify an app.
- If the screenshot service reports the device is locked or unavailable, report that state instead of claiming screenshot success.
- Do not overwrite an existing output unless the user requested that exact path or `--overwrite` is supplied.
