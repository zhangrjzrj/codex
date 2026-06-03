---
name: beyond-compare-opener
description: "Open two user-named local files or folders in Beyond Compare. Use when the user asks to compare two paths with an editor or diff tool, including Chinese requests equivalent to 'use Beyond Compare to compare A and B', 'compare these two files', or 'diff these two folders'."
---

# Beyond Compare Opener

## Workflow

1. Resolve exactly two requested paths.
   - If the user gives absolute paths, use them directly.
   - If the user gives relative paths, resolve them from the current workspace first.
   - If the user gives descriptive names, search with `rg --files` or targeted `Get-ChildItem`.
   - If fewer or more than two plausible paths are available, ask a concise clarification.

2. Verify both paths exist before opening Beyond Compare.
   - Files and directories are both valid.
   - If either path is missing, report the missing resolved path and do not launch.

3. Open Beyond Compare.
   - Prefer `BCompare` on `PATH`.
   - If unavailable, try `BComp` on `PATH`.
   - Otherwise try common Windows install paths such as:
     - `D:\Program Files\Beyond Compare 4\BCompare.exe`
     - `C:\Program Files\Beyond Compare 5\BCompare.exe`
     - `C:\Program Files\Beyond Compare 4\BCompare.exe`
     - `C:\Program Files (x86)\Beyond Compare 5\BCompare.exe`
     - `C:\Program Files (x86)\Beyond Compare 4\BCompare.exe`
   - Use `Start-Process -FilePath <bcompare_exe> -ArgumentList @(<left>, <right>) -WindowStyle Hidden` unless the user explicitly wants a visible launcher window. Beyond Compare itself will show normally.

4. If launching a GUI app requires approval, request escalation for the `Start-Process` command with a short justification.

## Response

After launching, reply with the two opened absolute paths. If Beyond Compare cannot be found, say so and provide the two paths that would have been compared.
