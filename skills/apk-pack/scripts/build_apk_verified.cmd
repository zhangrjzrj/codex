@echo off
setlocal

if "%~1"=="" (
  echo Usage: build_apk_verified.cmd PROJECT_PATH PACKAGE_NAME [OFFLINE_PROJECT_PATH]
  exit /b 2
)

set "PROJECT_PATH=%~1"
set "PACKAGE_NAME=%~2"
set "OFFLINE_PROJECT_PATH=%~3"
if "%PACKAGE_NAME%"=="" (
  echo PACKAGE_NAME is required.
  exit /b 2
)

set "VERIFY_FILE=%PROJECT_PATH%\.apk_verify_tag"
if not exist "%VERIFY_FILE%" (
  echo verify tag file missing: %VERIFY_FILE%
  exit /b 2
)

for /f "usebackq tokens=* delims=" %%i in ("%VERIFY_FILE%") do (
  set "APK_VERIFY_TAG=%%i"
  goto got_tag
)

:got_tag
if "%APK_VERIFY_TAG%"=="" (
  echo verify tag is empty in file: %VERIFY_FILE%
  exit /b 2
)

set "PS1=%~dp0build_apk.ps1"
if not exist "%PS1%" (
  echo script not found: %PS1%
  exit /b 2
)

if "%OFFLINE_PROJECT_PATH%"=="" (
  powershell -ExecutionPolicy Bypass -File "%PS1%" -ProjectPath "%PROJECT_PATH%" -PackageName "%PACKAGE_NAME%" -Mode local
) else (
  powershell -ExecutionPolicy Bypass -File "%PS1%" -ProjectPath "%PROJECT_PATH%" -PackageName "%PACKAGE_NAME%" -Mode local -OfflineProjectPath "%OFFLINE_PROJECT_PATH%"
)

exit /b %ERRORLEVEL%
