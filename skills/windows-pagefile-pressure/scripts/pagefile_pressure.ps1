param(
    [switch]$StatusOnly,
    [switch]$Pressure,
    [switch]$FillDrive,
    [switch]$ReleaseFill,
    [string]$Drive = "E",
    [int]$TargetDriveFreeMB = 0,
    [int]$ChunkMB = 256,
    [int]$MaxChunks = 128,
    [int]$TouchStrideKB = 4,
    [int]$SleepMs = 50,
    [int]$RetouchSleepMs = 250,
    [int]$TargetHeadroomMB = 1024,
    [int]$SafetyMarginMB = 256,
    [switch]$ShowPageFile
)

$ErrorActionPreference = "Stop"
$buffers = New-Object System.Collections.Generic.List[object]
$driveName = $Drive.TrimEnd(":")
$fillPrefix = "codex_pagefile_pressure_fill"

function Get-PressureStatus {
    $memory = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
    $os = Get-CimInstance Win32_OperatingSystem
    $pageFiles = Get-CimInstance Win32_PageFileUsage
    $driveInfo = Get-PSDrive -Name $driveName -ErrorAction SilentlyContinue
    $pageFileCurrentMB = 0
    foreach ($pf in $pageFiles) {
        $pageFileCurrentMB += [int]$pf.CurrentUsage
    }

    [pscustomobject]@{
        Drive              = $driveName
        DriveFreeMB        = if ($driveInfo) { [math]::Round($driveInfo.Free / 1MB, 1) } else { $null }
        FreePhysMB         = [math]::Round($os.FreePhysicalMemory / 1024, 1)
        FreeVirtMB         = [math]::Round($os.FreeVirtualMemory / 1024, 1)
        CommittedMB        = [math]::Round($memory.CommittedBytes / 1MB, 1)
        CommitLimitMB      = [math]::Round($memory.CommitLimit / 1MB, 1)
        HeadroomMB         = [math]::Round(($memory.CommitLimit - $memory.CommittedBytes) / 1MB, 1)
        HeldMB             = [math]::Round($buffers.Count * $ChunkMB, 1)
        PageFileCurrentMB  = $pageFileCurrentMB
        PageFiles          = $pageFiles
    }
}

function Show-PressureStatus {
    param([int]$Index = -1)
    $s = Get-PressureStatus
    $pfText = ($s.PageFiles | ForEach-Object {
        "{0}:alloc={1}MB current={2}MB peak={3}MB" -f $_.Name, $_.AllocatedBaseSize, $_.CurrentUsage, $_.PeakUsage
    }) -join " "
    Write-Host ("idx={0} held={1}MB commit={2}/{3}MB headroom={4}MB freePhys={5}MB freeVirt={6}MB {7}:free={8}MB pagefile={9}" -f `
        $Index, $s.HeldMB, $s.CommittedMB, $s.CommitLimitMB, $s.HeadroomMB, $s.FreePhysMB, $s.FreeVirtMB, $s.Drive, $s.DriveFreeMB, $pfText)

    if ($ShowPageFile) {
        $s.PageFiles | Select-Object Name, AllocatedBaseSize, CurrentUsage, PeakUsage | Format-Table -AutoSize
    }
}

function Touch-Buffer {
    param([byte[]]$Buffer)
    $stride = [Math]::Max(1, $TouchStrideKB) * 1KB
    for ($p = 0; $p -lt $Buffer.Length; $p += $stride) {
        $Buffer[$p] = [byte](($Buffer[$p] + 1) % 256)
    }
}

function Fill-DriveToTarget {
    if ($TargetDriveFreeMB -le 0) {
        throw "TargetDriveFreeMB must be > 0 for FillDrive."
    }
    $driveInfo = Get-PSDrive -Name $driveName
    $targetBytes = [int64]$TargetDriveFreeMB * 1MB
    $fillBytes = [int64]($driveInfo.Free - $targetBytes)
    if ($fillBytes -le 0) {
        Write-Host ("No fill needed. {0}: free={1:N1}MB target={2}MB" -f $driveName, ($driveInfo.Free / 1MB), $TargetDriveFreeMB)
        return
    }

    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $path = "{0}:\{1}_{2}.bin" -f $driveName, $fillPrefix, $stamp
    Write-Host ("Creating fill file {0} size={1:N1}MB" -f $path, ($fillBytes / 1MB))
    fsutil file createnew $path $fillBytes | Out-Host
    Show-PressureStatus
}

function Release-FillFiles {
    $root = "{0}:\" -f $driveName
    $files = Get-ChildItem -LiteralPath $root -Filter "$fillPrefix*.bin" -File -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        Write-Host ("Deleting {0} size={1:N1}MB" -f $file.FullName, ($file.Length / 1MB))
        Remove-Item -LiteralPath $file.FullName -Force
    }
    Show-PressureStatus
}

function Run-Pressure {
    for ($i = 0; $i -lt $MaxChunks; $i++) {
        $s = Get-PressureStatus
        if ($s.HeadroomMB -le ($TargetHeadroomMB + $ChunkMB + $SafetyMarginMB)) {
            Write-Host ("stop before alloc: headroom {0} <= target+chunk+margin ({1}+{2}+{3}) MB" -f $s.HeadroomMB, $TargetHeadroomMB, $ChunkMB, $SafetyMarginMB)
            break
        }

        try {
            $arr = New-Object byte[] ([int64]$ChunkMB * 1MB)
            Touch-Buffer -Buffer $arr
            $buffers.Add($arr) | Out-Null
            Show-PressureStatus -Index $i
            Start-Sleep -Milliseconds $SleepMs
        }
        catch {
            Write-Host ("allocation failed at chunk {0}: {1}" -f $i, $_.Exception.Message)
            break
        }
    }

    Write-Host "holding buffers. press Enter to release."
    while ($true) {
        try {
            if ([Console]::KeyAvailable) {
                $key = [Console]::ReadKey($true)
                if ($key.Key -eq [ConsoleKey]::Enter) { break }
            }
        }
        catch {
        }
        foreach ($buf in $buffers) {
            Touch-Buffer -Buffer $buf
        }
        Show-PressureStatus -Index $buffers.Count
        Start-Sleep -Milliseconds $RetouchSleepMs
    }

    $buffers.Clear()
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    Write-Host "released."
}

if ($StatusOnly) {
    Show-PressureStatus
    exit 0
}
if ($FillDrive) {
    Fill-DriveToTarget
    exit 0
}
if ($ReleaseFill) {
    Release-FillFiles
    exit 0
}
if ($Pressure) {
    Run-Pressure
    exit 0
}

Show-PressureStatus
