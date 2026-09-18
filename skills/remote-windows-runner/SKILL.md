---
name: "remote-windows-runner"
description: "Operate a registered Windows runner over SSH for remote command execution, file transfer, environment checks, and evidence collection; use when a workflow must run on a specific Windows host, without embedding Android or application-test logic."
---

# Remote Windows Runner

Use this skill when a workflow needs a registered Windows machine as an execution node. Keep this skill focused on transport and host operations. Compose it with application-specific skills such as ADB or Messiah test orchestration when the remote host runs those tools.

## Registered Host

The current runner is exposed through the local SSH alias:

```text
android-runner
```

The alias is expected to resolve the host, account, and existing local SSH identity. Do not put passwords, private keys, or private key contents in this skill, scripts, logs, or project files.

## Preconditions

Before a mutating workflow, verify the transport and host identity:

```powershell
ssh -o BatchMode=yes android-runner "hostname"
```

The command must return the expected Windows host name without prompting for a password. If it prompts or fails, stop and repair SSH authentication before continuing.

For a new session, collect the minimum host facts needed by the workflow:

```powershell
ssh android-runner "ver"
ssh android-runner "whoami"
```

## Remote Commands

Use Windows command syntax when the SSH server invokes its default shell. For PowerShell scripts, send an explicitly encoded or quoted PowerShell command and avoid local-shell variable expansion. Prefer a temporary script transferred with `scp` when the command is more than a few statements.

Examples:

```powershell
ssh android-runner "hostname"
ssh android-runner "where adb"
scp .\artifact.zip android-runner:C:/Temp/artifact.zip
scp android-runner:C:/Temp/result.json .\artifacts\result.json
```

For paths, use Windows absolute paths with forward slashes in `scp` arguments or quote paths containing spaces. Keep generated logs, screenshots, and one-off diagnostics in the workflow's ignored evidence directory, not in the repository source tree.

## Execution Rules

- Confirm the target host with `hostname` before actions that install, delete, restart, or overwrite.
- Prefer idempotent checks before installation or service changes.
- Do not install Android tooling, manipulate devices, or define application test cases here; use the relevant ADB and test-loop skills after transport is verified.
- Do not silently retry, swallow errors, or continue after a failed remote command. Capture the exit code and output, then diagnose the first failure.
- For long-running GUI or test processes, start them in a controlled background process, record the PID, poll process/log progress, and stop on a fatal dialog, unresponsive state, or timeout.
- Transfer only the files required for the current workflow and verify their destination before execution.

## Evidence

Every remote execution round should retain:

1. The exact remote command or transferred script name.
2. The remote host name and account.
3. The exit code and concise stdout/stderr.
4. Paths to any result, log, screenshot, or dump pulled back locally.

The skill provides host transport only. The calling workflow decides pass/fail criteria and owns application-specific evidence interpretation.
