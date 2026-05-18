param(
    [string]$SourceRepo = "E:\messiah_h74\Encoder\NBSEncoder",
    [string]$BuildDir = "E:\messiah_h74\Encoder\build",
    [string]$ExePath = "E:\messiah_h74\Encoder\build\Release\NewBasisEncoder.exe",
    [string]$GuiWorkDir = "",
    [string]$BaseConfig = "",
    [int[]]$DilateValues = @(),
    [string]$OutputPrefix = "F:/messiah_h74/820_test_dither_edge",
    [switch]$Build,
    [switch]$NoRun
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($GuiWorkDir)) {
    $GuiWorkDir = "F:\$([char]0x3010)GUI$([char]0x3011)NBSEncoder"
}
if ([string]::IsNullOrWhiteSpace($BaseConfig)) {
    $BaseConfig = Join-Path $GuiWorkDir "config.txt"
}

if ($Build) {
    cmake --build $BuildDir --config Release --target NewBasisEncoder
}

if (!(Test-Path -LiteralPath $ExePath)) {
    throw "Encoder exe not found: $ExePath"
}
if (!(Test-Path -LiteralPath $BaseConfig)) {
    throw "Base config not found: $BaseConfig"
}

$enc = [System.Text.Encoding]::Default
$baseText = [System.IO.File]::ReadAllText($BaseConfig, $enc)
$runs = @()

if ($DilateValues.Count -gt 0) {
    foreach ($d in $DilateValues) {
        $text = $baseText
        $nbsPath = "${OutputPrefix}_dilate$d.nbs"
        $text = [regex]::Replace($text, '(?m)^\s*nbs_file_path\s*=.*$', "nbs_file_path = $nbsPath")
        if ($text -match '(?m)^\s*new_depth_dither\s*=') {
            $text = [regex]::Replace($text, '(?m)^\s*new_depth_dither\s*=.*$', 'new_depth_dither = 1')
        } else {
            $text += "`r`nnew_depth_dither = 1`r`n"
        }
        if ($text -match '(?m)^\s*new_depth_dither_edge_dilate_px\s*=') {
            $text = [regex]::Replace($text, '(?m)^\s*new_depth_dither_edge_dilate_px\s*=.*$', "new_depth_dither_edge_dilate_px = $d")
        } else {
            $text += "`r`nnew_depth_dither_edge_dilate_px = $d`r`n"
        }

        $configPath = Join-Path $GuiWorkDir "config_dither_dilate$d.txt"
        [System.IO.File]::WriteAllText($configPath, $text, $enc)
        $runs += [PSCustomObject]@{
            Name = "dilate$d"
            Config = (Split-Path $configPath -Leaf)
            Output = $nbsPath -replace '/', '\'
            ConsoleLog = "run_dither_dilate$d.console.log"
        }
    }
} else {
    $runs += [PSCustomObject]@{
        Name = "config"
        Config = (Split-Path $BaseConfig -Leaf)
        Output = $null
        ConsoleLog = "run_encoder.console.log"
    }
}

if (!$NoRun) {
    Push-Location $GuiWorkDir
    try {
        foreach ($run in $runs) {
            Write-Host "=== encode $($run.Name) ==="
            & $ExePath $run.Config *> $run.ConsoleLog
            $code = $LASTEXITCODE
            Write-Host "exit=$code"
            if ($code -ne 0) {
                throw "Encode failed for $($run.Name) with exit code $code"
            }
        }
    } finally {
        Pop-Location
    }
}

$summary = @()
foreach ($run in $runs) {
    $outputPath = $run.Output
    if (!$outputPath) {
        $configText = [System.IO.File]::ReadAllText((Join-Path $GuiWorkDir $run.Config), $enc)
        $m = [regex]::Match($configText, '(?m)^\s*nbs_file_path\s*=\s*(.+?)\s*$')
        if ($m.Success) { $outputPath = $m.Groups[1].Value -replace '/', '\' }
    }
    $item = if ($outputPath) { Get-Item -LiteralPath $outputPath -ErrorAction SilentlyContinue } else { $null }
    $summary += [PSCustomObject]@{
        Run = $run.Name
        Config = $run.Config
        Output = $outputPath
        Bytes = if ($item) { $item.Length } else { $null }
        MiB = if ($item) { [Math]::Round($item.Length / 1MB, 3) } else { $null }
        ConsoleLog = Join-Path $GuiWorkDir $run.ConsoleLog
    }
}

$summary | Format-Table -AutoSize
