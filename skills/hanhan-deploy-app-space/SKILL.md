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
2. Run the unified deploy script from any workspace. The requested space, not the current directory, is the execution root:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\hanhan\<current-or-any-app-space>\scripts\deploy_app_space.ps1 -Space <space>
   ```
3. Use debug/visible mode only when requested:
   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\hanhan\<current-or-any-app-space>\scripts\deploy_app_space.ps1 -Space <space> -Mode debug
   ```
4. To deploy multiple spaces, run the same script once per space. Prefer serial APK builds:
   ```powershell
   foreach($s in 'app1','app2','app3','app4'){
     powershell -ExecutionPolicy Bypass -File D:\hanhan\app2\scripts\deploy_app_space.ps1 -Space $s
   }
   ```
5. Open the APK output directory if the user is installing on a real device.

The script performs the gates, Linux backend restart, Windows forwarding, APK build/install/launch, generated-space verification, and login verification.

## Guardrails

- Do not edit `config/spaceConfig.json`; it is deprecated local artifact.
- Do not add fallback config, default app selection, try/catch swallowing, sleeps, or retries without explicit user approval.
- Do not deploy a different space because the requested one is stuck; fix or report the requested space.
- Do not manually rebuild the old command sequence unless `deploy_app_space.ps1` itself is broken; fix the script instead.
- Do not overwrite unrelated dirty work in `D:\hanhan\ai_backend`, `D:\hanhan\app`, or app1-4 workspaces.
- Treat root-path HTTP `404` as a possible Webman liveness signal, but still verify the intended route or login endpoint before declaring success.
