---
name: "hanhan-deploy-app-space"
description: "Deploy and verify a Hanhan/Duomilu app space such as app1, app2, app3, or app4. Use when the user says '部署 app2', asks to prepare a visible/backend instance for an app space, package/install an app-space APK, restart the matching Linux backend, start Windows forwarding, or validate frontend/backend space configuration alignment."
---

# Hanhan Deploy App Space

## Principle

Deploy by explicit space. Never silently fall back to another app, default port, default runtime root, or generated local config.

The selected space must drive both sides:

- Frontend: `D:\hanhan\<space>\config\spaces\<space>.json`
- Backend: `D:\hanhan\ai_backend\config\backend_instances.php`

If a required config is missing or mismatched, stop and report the exact mismatch.

## Standard Flow

1. Parse the requested space from the user prompt. Accept only `app1`, `app2`, `app3`, or `app4`.
2. Inspect `D:\hanhan\<space>\config\spaces\<space>.json` and confirm `spaceName`, `deviceId`, `httpPort`, `wsPort`, `protectedApiKey`, `projectRoot`, and `androidShellRoot`.
3. Run frontend gates from the selected workspace:
   ```powershell
   node scripts\verify_local_debug_config_source.js
   node scripts\verify_space_config_alignment.js
   ```
4. Restart the matching Linux backend with explicit runtime root:
   ```powershell
   ssh -i C:/Users/zhangrjzrj/.ssh/app4_vmware_cdp_ed25519 -o BatchMode=yes zhangrjzrj@192.168.200.128 "cd /home/zhangrjzrj/hanhan-runtime/ai_backend-live && BACKEND_RUNTIME_ROOT=/home/zhangrjzrj/hanhan-runtime/ai_backend ./scripts/restart_backend_instance_linux.sh <space>"
   ```
5. Start or verify Windows forwarding for the same space:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\hanhan\ai_backend\scripts\start_app_backend_forwards.ps1 -InstanceId <space>
   ```
6. Build, install, and launch the selected app workspace:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\hanhan\<space>\scripts\export_pack_install.ps1 -VerifyText "<login-phone-or-space-marker>" -CleanBeforeBuild
   ```
7. Verify the generated frontend selector:
   ```powershell
   Get-Content D:\hanhan\<space>\config\selectedSpace.generated.js
   ```
   It must contain only the requested space.
8. Verify backend reachability on the configured HTTP port and login if credentials are known.
9. Open the APK output directory if the user is installing on a real device.

## Guardrails

- Do not edit `config/spaceConfig.json`; it is deprecated local artifact.
- Do not add fallback config, default app selection, try/catch swallowing, sleeps, or retries without explicit user approval.
- Do not deploy a different space because the requested one is stuck; fix or report the requested space.
- Do not overwrite unrelated dirty work in `D:\hanhan\ai_backend`, `D:\hanhan\app`, or app1-4 workspaces.
- Treat root-path HTTP `404` as a possible Webman liveness signal, but still verify the intended route or login endpoint before declaring success.
