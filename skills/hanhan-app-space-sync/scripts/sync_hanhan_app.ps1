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
if ($null -ne (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$defaultPreservePaths = @(
    'config/localDebug.js',
    'scripts/auto_pack_on_export.ps1',
    'scripts/export_app_resources.ps1',
    'scripts/export_pack_install.ps1',
    'scripts/onekey_pack_install.ps1',
    'scripts/send_duomilu_prompt.ps1'
)

$skipPromotePaths = @(
    '背景.txt'
)

$defaultSharedPathPrefixes = @(
    'api/',
    'common/',
    'components/',
    'config/',
    'docs/',
    'hybrid/',
    'js_sdk/',
    'pages/',
    'static/',
    'store/',
    'uni_modules/',
    'uniCloud/',
    'utils/'
)

function Invoke-Git {
    param(
        [string]$Repo,
        [string[]]$GitArgs,
        [switch]$AllowFailure
    )
    $tempBase = Join-Path ([System.IO.Path]::GetTempPath()) ("hanhan-git-" + [guid]::NewGuid().ToString("N"))
    $stdoutPath = "$tempBase.out"
    $stderrPath = "$tempBase.err"
    try {
        $argumentList = @('-c', 'core.quotePath=false', '-C', $Repo) + $GitArgs
        $process = Start-Process -FilePath 'git' -ArgumentList $argumentList -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        $code = $process.ExitCode
        $stdout = if (Test-Path $stdoutPath) { Get-Content -Raw $stdoutPath } else { '' }
        $stderr = if (Test-Path $stderrPath) { Get-Content -Raw $stderrPath } else { '' }
        $output = @($stdout, $stderr) -join ''
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
    if (-not $AllowFailure -and $code -ne 0) {
        throw "git -C $Repo $($GitArgs -join ' ') failed.`n$output"
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
    $normalizedPath = ''
    if (-not [string]::IsNullOrWhiteSpace($Path)) {
        $normalizedPath = $Path.Trim()
    }
    foreach ($item in $defaultPreservePaths) {
        if ($normalizedPath -ieq $item) {
            return $true
        }
    }
    return $false
}

function Test-SharedPath {
    param(
        [string]$Path
    )
    $normalizedPath = ([string]$Path).Trim().Replace('\', '/')
    if ([string]::IsNullOrWhiteSpace($normalizedPath)) {
        return $false
    }
    foreach ($item in $defaultPreservePaths) {
        $normalizedPreserve = $item.Replace('\', '/')
        if ($normalizedPath -ieq $normalizedPreserve) {
            return $true
        }
    }
    foreach ($prefix in $defaultSharedPathPrefixes) {
        if ($normalizedPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Test-SkipPromotePath {
    param(
        [string]$Path
    )
    $normalizedPath = ''
    if (-not [string]::IsNullOrWhiteSpace($Path)) {
        $normalizedPath = $Path.Trim()
    }
    foreach ($item in $skipPromotePaths) {
        if ($normalizedPath -ieq $item) {
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
    $result = Invoke-Git -Repo $Repo -GitArgs @('show', '--pretty=format:', '--name-only', $Commit)
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
    return (Invoke-Git -Repo $Repo -GitArgs @('show', '-s', '--format=%s', $Commit)).Output
}

function Get-CommitBodyFile {
    param(
        [string]$Repo,
        [string]$Commit,
        [string]$Dir
    )
    $message = (Invoke-Git -Repo $Repo -GitArgs @('show', '-s', '--format=%B', $Commit)).Output
    $path = Join-Path $Dir "$Commit-message.txt"
    Set-Content -LiteralPath $path -Value $message -Encoding UTF8
    return $path
}

function Get-DirtyEntries {
    param(
        [string]$Repo
    )
    $result = Invoke-Git -Repo $Repo -GitArgs @('status', '--porcelain')
    if ([string]::IsNullOrWhiteSpace($result.Output)) {
        return @()
    }
    return @($result.Output -split "`r?`n" | Where-Object { $_.Trim() -ne '' } | ForEach-Object {
            $line = $_
            $path = $line
            if ($line.Length -ge 3 -and $line[2] -eq ' ') {
                $path = $line.Substring(3)
            }
            elseif ($line.Length -ge 2 -and $line[1] -eq ' ') {
                $path = $line.Substring(2)
            }
            $path = ([string]$path).Trim()
            if ($path -match '^(.*)\s+->\s+(.*)$') {
                $path = $Matches[2].Trim()
            }
            [pscustomobject]@{
                Raw = $line
                Path = $path
                Preserved = (Test-PreservedPath -Path $path)
            }
        })
}

function Get-UnclassifiedPaths {
    param(
        [string]$Repo
    )
    $result = Invoke-Git -Repo $Repo -GitArgs @('ls-files', '--others', '--exclude-standard')
    if ([string]::IsNullOrWhiteSpace($result.Output)) {
        return @()
    }
    return @(
        $result.Output -split "`r?`n" |
        Where-Object { $_.Trim() -ne '' } |
        ForEach-Object {
            $path = ([string]$_).Trim().Replace('\', '/')
            if ((Test-PreservedPath -Path $path) -or (Test-SharedPath -Path $path) -or (Test-SkipPromotePath -Path $path)) {
                return
            }
            [pscustomobject]@{
                Path = $path
                Classification = 'unclassified-untracked'
            }
        } |
        Where-Object { $null -ne $_ }
    )
}

function Get-SpaceRiskReport {
    param(
        [string]$MainPath,
        [string]$SpaceName
    )
    $spacePath = Join-Path $Root $SpaceName
    $trackedDiff = Invoke-Git -Repo $spacePath -GitArgs @('diff', '--name-only', "$Branch..HEAD")
    $paths = @()
    if (-not [string]::IsNullOrWhiteSpace($trackedDiff.Output)) {
        $paths += @($trackedDiff.Output -split "`r?`n" | Where-Object { $_.Trim() -ne '' })
    }
    $paths += @(Get-UnclassifiedPaths -Repo $spacePath | Select-Object -ExpandProperty Path)
    $paths = @($paths | ForEach-Object { ([string]$_).Trim().Replace('\', '/') } | Where-Object { $_ -ne '' } | Sort-Object -Unique)

    $unclassified = @()
    foreach ($path in $paths) {
        if ((Test-PreservedPath -Path $path) -or (Test-SharedPath -Path $path) -or (Test-SkipPromotePath -Path $path)) {
            continue
        }
        $unclassified += $path
    }

    return [pscustomobject]@{
        space = $SpaceName
        unclassified_paths = $unclassified
    }
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
        $aheadBehind = (Invoke-Git -Repo $MainPath -GitArgs @('rev-list', '--left-right', '--count', "HEAD...local_$name/$Branch")).Output
        $risk = Get-SpaceRiskReport -MainPath $MainPath -SpaceName $name
        $rows += [pscustomobject]@{
            space = $name
            main_vs_space = $aheadBehind
            dirty = (Get-DirtyEntries -Repo $spacePath).Count
            unclassified_paths = $risk.unclassified_paths
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
        $sharedRemoteUrl = (Invoke-Git -Repo $MainPath -GitArgs @('remote', 'get-url', $SharedRemote)).Output
        $tempRemoteCheck = Invoke-Git -Repo $tempMain -GitArgs @('remote', 'get-url', $SharedRemote) -AllowFailure
        if ($tempRemoteCheck.Code -ne 0) {
            Invoke-Git -Repo $tempMain -GitArgs @('remote', 'add', $SharedRemote, $sharedRemoteUrl) | Out-Null
        }
        Invoke-Git -Repo $tempMain -GitArgs @('checkout', '-B', $Branch, $Branch) | Out-Null
        Invoke-Git -Repo $tempMain -GitArgs @('fetch', $SharedRemote, $Branch) | Out-Null
        foreach ($name in $Spaces) {
            $spacePath = Join-Path $Root $name
            $risk = Get-SpaceRiskReport -MainPath $MainPath -SpaceName $name
            if ($risk.unclassified_paths.Count -gt 0) {
                $joined = $risk.unclassified_paths -join "`n"
                throw "Workspace $name has unclassified paths. Classify them as shared or preserved before promote-main.`n$joined"
            }
            $remoteName = "src_$name"
            $hasRemote = Invoke-Git -Repo $tempMain -GitArgs @('remote', 'get-url', $remoteName) -AllowFailure
            if ($hasRemote.Code -ne 0) {
                Invoke-Git -Repo $tempMain -GitArgs @('remote', 'add', $remoteName, $spacePath) | Out-Null
            }
            Invoke-Git -Repo $tempMain -GitArgs @('fetch', $remoteName, $Branch) | Out-Null
        }

        $actions = @()
        foreach ($name in $Spaces) {
            $remoteName = "src_$name"
            $commitList = (Invoke-Git -Repo $tempMain -GitArgs @('rev-list', '--reverse', '--right-only', '--cherry-pick', "$Branch...$remoteName/$Branch")).Output
            if ([string]::IsNullOrWhiteSpace($commitList)) {
                continue
            }
            foreach ($commit in ($commitList -split "`r?`n" | Where-Object { $_.Trim() -ne '' })) {
                $subject = Get-CommitSubject -Repo $tempMain -Commit $commit
                if ($subject -match '背景文档|背景入口|标准发布流程') {
                    $actions += [pscustomobject]@{ space = $name; commit = $commit; action = 'skip-background-doc-history'; subject = $subject }
                    continue
                }
                $files = Get-CommitFiles -Repo $tempMain -Commit $commit
                $nonSkippedFiles = @($files | Where-Object { -not (Test-SkipPromotePath -Path $_) })
                if ($nonSkippedFiles.Count -eq 0) {
                    $actions += [pscustomobject]@{ space = $name; commit = $commit; action = 'skip-deprecated-path-only'; subject = $subject }
                    continue
                }
                $sharedFiles = @($files | Where-Object { -not (Test-PreservedPath -Path $_) })
                if ($sharedFiles.Count -eq 0) {
                    $actions += [pscustomobject]@{ space = $name; commit = $commit; action = 'skip-local-only'; subject = $subject }
                    continue
                }

                Invoke-Git -Repo $tempMain -GitArgs @('cherry-pick', '--no-commit', $commit) | Out-Null
                $restoreTargets = @($files | Where-Object { Test-PreservedPath -Path $_ })
                if ($restoreTargets.Count -gt 0) {
                    Invoke-Git -Repo $tempMain -GitArgs (@('restore', '--source=HEAD', '--staged', '--worktree', '--') + $restoreTargets) | Out-Null
                }

                $staged = (Invoke-Git -Repo $tempMain -GitArgs @('diff', '--cached', '--name-only')).Output
                if ([string]::IsNullOrWhiteSpace($staged)) {
                    Invoke-Git -Repo $tempMain -GitArgs @('reset', '--hard', 'HEAD') | Out-Null
                    $actions += [pscustomobject]@{ space = $name; commit = $commit; action = 'skip-empty-after-filter'; subject = $subject }
                    continue
                }

                $messageFile = Get-CommitBodyFile -Repo $tempMain -Commit $commit -Dir $tempRoot
                Invoke-Git -Repo $tempMain -GitArgs @('commit', '--file', $messageFile) | Out-Null
                $actions += [pscustomobject]@{ space = $name; commit = $commit; action = 'promoted'; subject = $subject }
            }
        }

        if ($Push) {
            Invoke-Git -Repo $tempMain -GitArgs @('push', $SharedRemote, "${Branch}:$Branch") | Out-Null
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
    $risk = Get-SpaceRiskReport -MainPath $mainPath -SpaceName $Space
    if ($risk.unclassified_paths.Count -gt 0) {
        throw "Workspace $Space has unclassified paths and cannot be refreshed safely.`n$($risk.unclassified_paths -join "`n")"
    }
    $dirtyEntries = Get-DirtyEntries -Repo $spacePath
    $dirtyNonPreserved = @($dirtyEntries | Where-Object { -not (Test-PreservedPath -Path $_.Path) })
    if ($dirtyNonPreserved.Count -gt 0) {
        throw "Workspace $Space has dirty non-preserved files and cannot be refreshed safely.`n$($dirtyNonPreserved.Raw -join "`n")"
    }

    $preservedBackupDir = $null
    $preservedPaths = @()
    try {
        if ($dirtyEntries.Count -gt 0) {
            $preservedPaths = @($dirtyEntries | Select-Object -ExpandProperty Path -Unique)
            $preservedBackupDir = New-TempDir
            foreach ($path in $preservedPaths) {
                $sourcePath = Join-Path $spacePath $path
                if (-not (Test-Path -LiteralPath $sourcePath)) {
                    continue
                }
                $backupPath = Join-Path $preservedBackupDir $path
                $backupParent = Split-Path -Parent $backupPath
                if ($backupParent) {
                    New-Item -ItemType Directory -Force -Path $backupParent | Out-Null
                }
                Copy-Item -LiteralPath $sourcePath -Destination $backupPath -Force
            }
            Invoke-Git -Repo $spacePath -GitArgs (@('restore', '--source=HEAD', '--staged', '--worktree', '--') + $preservedPaths) | Out-Null
        }
        Invoke-Git -Repo $spacePath -GitArgs @('fetch', 'origin', $Branch) | Out-Null
        Invoke-Git -Repo $spacePath -GitArgs @('rebase', "origin/$Branch") | Out-Null
        if ($preservedPaths.Count -gt 0 -and $preservedBackupDir) {
            foreach ($path in $preservedPaths) {
                $backupPath = Join-Path $preservedBackupDir $path
                if (-not (Test-Path -LiteralPath $backupPath)) {
                    continue
                }
                $targetPath = Join-Path $spacePath $path
                $targetParent = Split-Path -Parent $targetPath
                if ($targetParent) {
                    New-Item -ItemType Directory -Force -Path $targetParent | Out-Null
                }
                Copy-Item -LiteralPath $backupPath -Destination $targetPath -Force
            }
        }
        return [pscustomobject]@{
            space = $Space
            rebased_to = "origin/$Branch"
            dirty_preserved_restored = ($preservedPaths.Count -gt 0)
        }
    }
    catch {
        $rebaseState = Join-Path $spacePath '.git\rebase-merge'
        if (Test-Path $rebaseState) {
            Invoke-Git -Repo $spacePath -GitArgs @('rebase', '--abort') -AllowFailure | Out-Null
        }
        throw
    }
    finally {
        if ($preservedBackupDir -and (Test-Path $preservedBackupDir)) {
            Remove-Item -LiteralPath $preservedBackupDir -Recurse -Force -ErrorAction SilentlyContinue
        }
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
