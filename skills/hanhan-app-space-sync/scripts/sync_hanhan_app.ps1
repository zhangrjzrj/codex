param(
    [ValidateSet('inventory', 'promote-main', 'refresh-space')]
    [string]$Mode = 'inventory',
    [string]$Root = 'D:\hanhan',
    [string]$MainRepo = 'app',
    [string[]]$Spaces = @('app1', 'app2', 'app3', 'app4'),
    [string]$Space,
    [string]$Branch = 'app_private',
    [string]$SharedRemote = 'private',
    [switch]$Push
)

$ErrorActionPreference = 'Stop'

$defaultPreservePaths = @(
    'config/localDebug.js',
    'scripts/auto_pack_on_export.ps1',
    'scripts/export_app_resources.ps1',
    'scripts/export_pack_install.ps1',
    'scripts/onekey_pack_install.ps1',
    'scripts/send_duomilu_prompt.ps1'
)

function Invoke-Git {
    param(
        [string]$Repo,
        [string[]]$Args,
        [switch]$AllowFailure
    )
    $output = & git -C $Repo @Args 2>&1
    $code = $LASTEXITCODE
    if (-not $AllowFailure -and $code -ne 0) {
        throw "git -C $Repo $($Args -join ' ') failed.`n$output"
    }
    return [pscustomobject]@{
        Code = $code
        Output = ($output -join "`n").Trim()
    }
}

function Test-PreservedPath {
    param(
        [string]$Path
    )
    foreach ($item in $defaultPreservePaths) {
        if ($Path -ieq $item) {
            return $true
        }
    }
    return $false
}

function Get-CommitFiles {
    param(
        [string]$Repo,
        [string]$Commit
    )
    $result = Invoke-Git -Repo $Repo -Args @('show', '--pretty=format:', '--name-only', $Commit)
    if ([string]::IsNullOrWhiteSpace($result.Output)) {
        return @()
    }
    return @($result.Output -split "`r?`n" | Where-Object { $_.Trim() -ne '' })
}

function Get-CommitSubject {
    param(
        [string]$Repo,
        [string]$Commit
    )
    return (Invoke-Git -Repo $Repo -Args @('show', '-s', '--format=%s', $Commit)).Output
}

function Get-CommitBodyFile {
    param(
        [string]$Repo,
        [string]$Commit,
        [string]$Dir
    )
    $message = (Invoke-Git -Repo $Repo -Args @('show', '-s', '--format=%B', $Commit)).Output
    $path = Join-Path $Dir "$Commit-message.txt"
    Set-Content -LiteralPath $path -Value $message -Encoding UTF8
    return $path
}

function Get-DirtyEntries {
    param(
        [string]$Repo
    )
    $result = Invoke-Git -Repo $Repo -Args @('status', '--porcelain')
    if ([string]::IsNullOrWhiteSpace($result.Output)) {
        return @()
    }
    return @($result.Output -split "`r?`n" | Where-Object { $_.Trim() -ne '' } | ForEach-Object {
            $line = $_
            $path = $line.Substring(3)
            [pscustomobject]@{
                Raw = $line
                Path = $path
                Preserved = (Test-PreservedPath -Path $path)
            }
        })
}

function New-TempDir {
    $dir = Join-Path ([System.IO.Path]::GetTempPath()) ("hanhan-app-sync-" + [DateTime]::Now.ToString("yyyyMMdd-HHmmss-fff"))
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    return $dir
}

function Invoke-Inventory {
    param(
        [string]$MainPath
    )
    $rows = @()
    foreach ($name in $Spaces) {
        $spacePath = Join-Path $Root $name
        $aheadBehind = (Invoke-Git -Repo $MainPath -Args @('rev-list', '--left-right', '--count', "HEAD...local_$name/$Branch")).Output
        $rows += [pscustomobject]@{
            space = $name
            main_vs_space = $aheadBehind
            dirty = (Get-DirtyEntries -Repo $spacePath).Count
        }
    }
    return $rows
}

function Invoke-PromoteMain {
    param(
        [string]$MainPath
    )
    $tempRoot = New-TempDir
    $tempMain = Join-Path $tempRoot 'app-main'
    try {
        & git clone --shared $MainPath $tempMain | Out-Null
        Invoke-Git -Repo $tempMain -Args @('checkout', '-B', $Branch, $Branch) | Out-Null
        Invoke-Git -Repo $tempMain -Args @('fetch', $SharedRemote, $Branch) | Out-Null
        foreach ($name in $Spaces) {
            $spacePath = Join-Path $Root $name
            $remoteName = "src_$name"
            $hasRemote = Invoke-Git -Repo $tempMain -Args @('remote', 'get-url', $remoteName) -AllowFailure
            if ($hasRemote.Code -ne 0) {
                Invoke-Git -Repo $tempMain -Args @('remote', 'add', $remoteName, $spacePath) | Out-Null
            }
            Invoke-Git -Repo $tempMain -Args @('fetch', $remoteName, $Branch) | Out-Null
        }

        $actions = @()
        foreach ($name in $Spaces) {
            $remoteName = "src_$name"
            $commitList = (Invoke-Git -Repo $tempMain -Args @('rev-list', '--reverse', "$Branch..$remoteName/$Branch")).Output
            if ([string]::IsNullOrWhiteSpace($commitList)) {
                continue
            }
            foreach ($commit in ($commitList -split "`r?`n" | Where-Object { $_.Trim() -ne '' })) {
                $files = Get-CommitFiles -Repo $tempMain -Commit $commit
                $sharedFiles = @($files | Where-Object { -not (Test-PreservedPath -Path $_) })
                if ($sharedFiles.Count -eq 0) {
                    $actions += [pscustomobject]@{ space = $name; commit = $commit; action = 'skip-local-only'; subject = (Get-CommitSubject -Repo $tempMain -Commit $commit) }
                    continue
                }

                Invoke-Git -Repo $tempMain -Args @('cherry-pick', '--no-commit', $commit) | Out-Null
                $restoreTargets = @($files | Where-Object { Test-PreservedPath -Path $_ })
                if ($restoreTargets.Count -gt 0) {
                    Invoke-Git -Repo $tempMain -Args (@('restore', '--source=HEAD', '--staged', '--worktree', '--') + $restoreTargets) | Out-Null
                }

                $staged = (Invoke-Git -Repo $tempMain -Args @('diff', '--cached', '--name-only')).Output
                if ([string]::IsNullOrWhiteSpace($staged)) {
                    Invoke-Git -Repo $tempMain -Args @('reset', '--hard', 'HEAD') | Out-Null
                    $actions += [pscustomobject]@{ space = $name; commit = $commit; action = 'skip-empty-after-filter'; subject = (Get-CommitSubject -Repo $tempMain -Commit $commit) }
                    continue
                }

                $messageFile = Get-CommitBodyFile -Repo $tempMain -Commit $commit -Dir $tempRoot
                Invoke-Git -Repo $tempMain -Args @('commit', '--file', $messageFile) | Out-Null
                $actions += [pscustomobject]@{ space = $name; commit = $commit; action = 'promoted'; subject = (Get-CommitSubject -Repo $tempMain -Commit $commit) }
            }
        }

        if ($Push) {
            Invoke-Git -Repo $tempMain -Args @('push', $SharedRemote, "${Branch}:$Branch") | Out-Null
        }

        return $actions
    }
    finally {
        if (Test-Path $tempRoot) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }
}

function Invoke-RefreshSpace {
    if ([string]::IsNullOrWhiteSpace($Space)) {
        throw '-Space is required for refresh-space.'
    }
    $spacePath = Join-Path $Root $Space
    $dirtyEntries = Get-DirtyEntries -Repo $spacePath
    $dirtyNonPreserved = @($dirtyEntries | Where-Object { -not $_.Preserved })
    if ($dirtyNonPreserved.Count -gt 0) {
        throw "Workspace $Space has dirty non-preserved files and cannot be refreshed safely.`n$($dirtyNonPreserved.Raw -join "`n")"
    }

    $stashCreated = $false
    try {
        if ($dirtyEntries.Count -gt 0) {
            $paths = @($dirtyEntries | Select-Object -ExpandProperty Path -Unique)
            Invoke-Git -Repo $spacePath -Args (@('stash', 'push', '-m', "hanhan-app-space-sync-$Space") + @('--') + $paths) | Out-Null
            $stashCreated = $true
        }
        Invoke-Git -Repo $spacePath -Args @('fetch', 'origin', $Branch) | Out-Null
        Invoke-Git -Repo $spacePath -Args @('rebase', "origin/$Branch") | Out-Null
        if ($stashCreated) {
            $pop = Invoke-Git -Repo $spacePath -Args @('stash', 'pop') -AllowFailure
            if ($pop.Code -ne 0) {
                throw "stash pop failed for $Space.`n$($pop.Output)"
            }
        }
        return [pscustomobject]@{
            space = $Space
            rebased_to = "origin/$Branch"
            dirty_preserved_restored = $stashCreated
        }
    }
    catch {
        $rebaseState = Join-Path $spacePath '.git\rebase-merge'
        if (Test-Path $rebaseState) {
            Invoke-Git -Repo $spacePath -Args @('rebase', '--abort') -AllowFailure | Out-Null
        }
        throw
    }
}

$mainPath = Join-Path $Root $MainRepo

switch ($Mode) {
    'inventory' {
        Invoke-Inventory -MainPath $mainPath | ConvertTo-Json -Depth 4
    }
    'promote-main' {
        Invoke-PromoteMain -MainPath $mainPath | ConvertTo-Json -Depth 4
    }
    'refresh-space' {
        Invoke-RefreshSpace | ConvertTo-Json -Depth 4
    }
}
