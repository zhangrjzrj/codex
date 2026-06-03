---
name: sublime-file-opener
description: Open a user-named local file in Sublime Text. Use when the user asks to open a specific file in an editor, including Chinese requests equivalent to "use editor to open this file", "open with Sublime Text", "open xx file", or when they want the file opened instead of printed.
---

# Sublime File Opener

## Workflow

1. Resolve the requested file path.
   - If the user gives an absolute path, use it directly.
   - If the user gives a relative path, resolve it from the current workspace first.
   - If the user gives a descriptive name, search with `rg --files` or a targeted `Get-ChildItem`.

2. Verify the path exists and is a file before opening it.
   - If it does not exist, say the resolved path is missing and, when useful, suggest the closest known path.
   - Do not create a missing file unless the user explicitly asks to create it.

3. Open the file with Sublime Text.
   - Prefer `subl` if available on `PATH`.
   - Otherwise try common Windows install paths such as:
     - `C:\Program Files\Sublime Text\sublime_text.exe`
     - `C:\Program Files\Sublime Text 3\sublime_text.exe`
     - `C:\Program Files\Sublime Text 4\sublime_text.exe`
     - `%LOCALAPPDATA%\Programs\Sublime Text\sublime_text.exe`
   - Use `Start-Process -FilePath <sublime_exe> -ArgumentList @(<file>) -WindowStyle Hidden` for non-interactive launching unless the user explicitly wants a visible launcher window. Sublime itself will show normally.

4. If launching a GUI app requires approval, request escalation for the `Start-Process` command with a short justification.

## Response

After launching, reply with the opened absolute path. If Sublime Text cannot be found, say so and provide the file path that would have been opened.
