---
name: "windows-uia-operator"
description: "Inspect and operate Windows desktop UI through Microsoft UI Automation with minimal keyboard/mouse interference. Use when Codex needs to enumerate Windows windows, dump an accessibility/control tree, invoke buttons/menu items, set edit values, select list items, handle system dialogs, file pickers, installer forms, or fill and submit ordinary desktop launch/configuration pages such as RenderDoc's launch tab when browser, ADB, and app-specific APIs do not cover the desktop shell."
---

# Windows UIA Operator

Use this skill for Windows desktop GUI tasks that expose a UI Automation tree. Prefer CDP/Playwright for web page content, ADB for Android, and app-specific APIs/logs when available. Use UIA for the Windows shell, native dialogs, file pickers, installers, and ordinary desktop controls.

## Operating Rules

- Start read-only: list windows or dump a UIA tree before acting.
- Prefer structured UIA patterns over real input: `InvokePattern`, `ValuePattern`, `SelectionItemPattern`, `ExpandCollapsePattern`, and `TogglePattern`.
- Avoid `SetFocus`, `SendKeys`, coordinates, or real mouse events unless explicitly needed as a fallback. Mark those actions as fallback in the report.
- Capture evidence around meaningful actions: UI tree before/after, target selector, action result, and screenshots when visual confirmation matters.
- Stop and report if a target window is missing, unresponsive, protected/elevated above the current process, or exposes only a blank/custom-rendered pane.

## Tool Script

Use `scripts/uia_operator.ps1` from this skill directory. It loads .NET UI Automation assemblies and supports JSON or text output.

Common commands:

```powershell
# List top-level windows.
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\windows-uia-operator\scripts\uia_operator.ps1" -Action list-windows

# Dump a bounded control tree for a window title.
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\windows-uia-operator\scripts\uia_operator.ps1" -Action dump-tree -TitleRegex "Notepad" -MaxDepth 4 -Json

# Invoke a button by name without moving the mouse.
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\windows-uia-operator\scripts\uia_operator.ps1" -Action invoke -TitleRegex "Save" -NameRegex "Save"

# Set text in an edit control by name or control type.
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\windows-uia-operator\scripts\uia_operator.ps1" -Action set-value -TitleRegex "Save" -ControlType Edit -Value "report.txt"
```

Selector options:

- `-TitleRegex`: regular expression for the top-level window title.
- `-ProcessName`: process name without `.exe`.
- `-ProcessId`: exact process id for tests or when multiple matching windows exist.
- `-NameRegex`: regular expression for the target control `Name`.
- `-AutomationId`: exact target control automation id.
- `-ControlType`: UIA control type name such as `Button`, `Edit`, `MenuItem`, `ListItem`, `ComboBox`, or `Document`.
- `-MaxDepth`: tree search/dump depth. Keep this bounded for large apps.

## Workflow

1. Identify the target process/window with `list-windows`.
2. Dump the tree with `dump-tree -MaxDepth 3` or `4`.
3. Choose the most stable selector in this order: `AutomationId`, `NameRegex + ControlType`, then `NameRegex` alone.
4. Run the structured action.
5. Dump the relevant tree again or take a screenshot if the visual state matters.
6. If UIA cannot see the inner controls, switch to a better channel: CDP for browser content, app APIs/logs, or screenshot/OCR fallback.

## RenderDoc Launch Flow

Use this flow when Codex needs to fill RenderDoc's `Launch Application` page without stealing the mouse or keyboard.

1. Confirm the top-level window exists with `-TitleRegex "RenderDoc v1\\..*"`.
2. Prefer UIA `Edit` controls and `ValuePattern` to fill:
   - `Program`
   - `Working Directory`
   - `Command-line Arguments`
3. Prefer stable selectors in this order:
   - label-specific `NameRegex` when the control exposes it
   - `AutomationId` if RenderDoc starts exposing one
   - bounded positional targeting among the window's `Edit` descendants only when the tree is stable and the first two options are unavailable
4. Submit with UIA `InvokePattern` on the `Launch` button.
5. Verify the outcome outside the form:
   - target process exists
   - expected command line is present
   - tool-specific readiness evidence appears in logs

For Unreal + RenderDoc specifically, treat `UIA filled the form` and `Launch completed a usable capture session` as two separate checks. Do not mark the flow complete until UE is alive with `-AttachRenderDoc` and the UE log shows `RenderDoc plugin is ready!`.

## Limits

- Windows UIA cannot see inside VMware/Linux guest controls; run AT-SPI, CDP, SSH, or tools inside the guest instead.
- Games, RenderDoc canvases, custom OpenGL/DirectX views, and some Electron/Qt/Java apps may expose only a large pane.
- Elevated/admin windows may require running the shell with matching integrity level.
- Password fields and secure desktop prompts may block value reads or actions by design.
