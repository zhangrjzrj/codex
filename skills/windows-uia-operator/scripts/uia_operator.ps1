param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('list-windows','dump-tree','invoke','set-value','toggle','select','expand','collapse')]
    [string]$Action,

    [string]$TitleRegex,
    [string]$ProcessName,
    [int]$ProcessId,
    [string]$NameRegex,
    [string]$AutomationId,
    [string]$ControlType,
    [string]$Value,
    [int]$MaxDepth = 5,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

function Convert-ControlTypeName {
    param([string]$Name)
    if ([string]::IsNullOrWhiteSpace($Name)) { return $null }
    $field = [System.Windows.Automation.ControlType].GetField($Name)
    if ($null -eq $field) {
        throw "Unknown ControlType '$Name'. Examples: Button, Edit, MenuItem, ListItem, ComboBox, Document."
    }
    return $field.GetValue($null)
}

function Get-ElementInfo {
    param($Element)
    if ($null -eq $Element) { return $null }
    $rect = $Element.Current.BoundingRectangle
    function Convert-RectNumber {
        param([double]$Number)
        if ([double]::IsInfinity($Number) -or [double]::IsNaN($Number)) { return $null }
        if ($Number -gt [int]::MaxValue) { return [int]::MaxValue }
        if ($Number -lt [int]::MinValue) { return [int]::MinValue }
        return [int]$Number
    }
    [ordered]@{
        name = $Element.Current.Name
        automationId = $Element.Current.AutomationId
        controlType = $Element.Current.ControlType.ProgrammaticName -replace '^ControlType\.',''
        className = $Element.Current.ClassName
        processId = $Element.Current.ProcessId
        isEnabled = $Element.Current.IsEnabled
        isOffscreen = $Element.Current.IsOffscreen
        rect = [ordered]@{
            x = Convert-RectNumber $rect.X
            y = Convert-RectNumber $rect.Y
            width = Convert-RectNumber $rect.Width
            height = Convert-RectNumber $rect.Height
        }
    }
}

function Write-Result {
    param($Data)
    if ($Json) {
        $Data | ConvertTo-Json -Depth 20
    } else {
        $Data | Format-List | Out-String
    }
}

function Test-WindowMatch {
    param($Element)
    if ($TitleRegex -and ($Element.Current.Name -notmatch $TitleRegex)) { return $false }
    if ($ProcessId -and ($Element.Current.ProcessId -ne $ProcessId)) { return $false }
    if ($ProcessName) {
        try {
            $p = Get-Process -Id $Element.Current.ProcessId -ErrorAction Stop
            if ($p.ProcessName -ne $ProcessName) { return $false }
        } catch {
            return $false
        }
    }
    return $true
}

function Get-TopWindows {
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $children = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
    $items = @()
    foreach ($child in $children) {
        if (Test-WindowMatch $child) {
            $items += $child
        }
    }
    return $items
}

function New-TargetCondition {
    $conditions = New-Object System.Collections.Generic.List[System.Windows.Automation.Condition]
    if ($AutomationId) {
        $conditions.Add((New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::AutomationIdProperty,
            $AutomationId
        )))
    }
    $ct = Convert-ControlTypeName $ControlType
    if ($null -ne $ct) {
        $conditions.Add((New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            $ct
        )))
    }
    if ($conditions.Count -eq 0) {
        return [System.Windows.Automation.Condition]::TrueCondition
    }
    if ($conditions.Count -eq 1) {
        return $conditions[0]
    }
    return New-Object System.Windows.Automation.AndCondition($conditions.ToArray())
}

function Test-TargetMatch {
    param($Element)
    if ($NameRegex -and ($Element.Current.Name -notmatch $NameRegex)) { return $false }
    return $true
}

function Find-Target {
    $windows = Get-TopWindows
    if ($windows.Count -eq 0) { throw "No top-level window matched TitleRegex='$TitleRegex' ProcessName='$ProcessName' ProcessId='$ProcessId'." }
    $condition = New-TargetCondition
    foreach ($window in $windows) {
        $found = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
        foreach ($item in $found) {
            if (Test-TargetMatch $item) {
                return [ordered]@{ window = $window; element = $item }
            }
        }
    }
    throw "No control matched NameRegex='$NameRegex' AutomationId='$AutomationId' ControlType='$ControlType'."
}

function Get-Pattern {
    param($Element, $Pattern)
    $out = $null
    if ($Element.TryGetCurrentPattern($Pattern, [ref]$out)) { return $out }
    return $null
}

function Get-TreeNode {
    param($Element, [int]$Depth)
    $node = Get-ElementInfo $Element
    if ($Depth -le 0) { return $node }
    $node.children = @()
    $children = $Element.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
    foreach ($child in $children) {
        $node.children += Get-TreeNode $child ($Depth - 1)
    }
    return $node
}

switch ($Action) {
    'list-windows' {
        $data = @()
        foreach ($window in Get-TopWindows) {
            $data += Get-ElementInfo $window
        }
        Write-Result ([ordered]@{ action = $Action; count = $data.Count; windows = $data })
    }
    'dump-tree' {
        $windows = Get-TopWindows
        if ($windows.Count -eq 0) { throw "No top-level window matched TitleRegex='$TitleRegex' ProcessName='$ProcessName' ProcessId='$ProcessId'." }
        $trees = @()
        foreach ($window in $windows) {
            $trees += Get-TreeNode $window $MaxDepth
        }
        Write-Result ([ordered]@{ action = $Action; count = $trees.Count; trees = $trees })
    }
    'invoke' {
        $target = Find-Target
        $pattern = Get-Pattern $target.element ([System.Windows.Automation.InvokePattern]::Pattern)
        if ($null -eq $pattern) { throw "Target does not support InvokePattern." }
        $pattern.Invoke()
        Write-Result ([ordered]@{ action = $Action; status = 'ok'; target = (Get-ElementInfo $target.element); inputMode = 'uia-pattern' })
    }
    'set-value' {
        if ($null -eq $Value) { throw "-Value is required for set-value." }
        $target = Find-Target
        $pattern = Get-Pattern $target.element ([System.Windows.Automation.ValuePattern]::Pattern)
        if ($null -eq $pattern) { throw "Target does not support ValuePattern." }
        if ($pattern.Current.IsReadOnly) { throw "Target ValuePattern is read-only." }
        $pattern.SetValue($Value)
        Write-Result ([ordered]@{ action = $Action; status = 'ok'; target = (Get-ElementInfo $target.element); inputMode = 'uia-pattern' })
    }
    'toggle' {
        $target = Find-Target
        $pattern = Get-Pattern $target.element ([System.Windows.Automation.TogglePattern]::Pattern)
        if ($null -eq $pattern) { throw "Target does not support TogglePattern." }
        $pattern.Toggle()
        Write-Result ([ordered]@{ action = $Action; status = 'ok'; target = (Get-ElementInfo $target.element); inputMode = 'uia-pattern' })
    }
    'select' {
        $target = Find-Target
        $pattern = Get-Pattern $target.element ([System.Windows.Automation.SelectionItemPattern]::Pattern)
        if ($null -eq $pattern) { throw "Target does not support SelectionItemPattern." }
        $pattern.Select()
        Write-Result ([ordered]@{ action = $Action; status = 'ok'; target = (Get-ElementInfo $target.element); inputMode = 'uia-pattern' })
    }
    'expand' {
        $target = Find-Target
        $pattern = Get-Pattern $target.element ([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
        if ($null -eq $pattern) { throw "Target does not support ExpandCollapsePattern." }
        $pattern.Expand()
        Write-Result ([ordered]@{ action = $Action; status = 'ok'; target = (Get-ElementInfo $target.element); inputMode = 'uia-pattern' })
    }
    'collapse' {
        $target = Find-Target
        $pattern = Get-Pattern $target.element ([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
        if ($null -eq $pattern) { throw "Target does not support ExpandCollapsePattern." }
        $pattern.Collapse()
        Write-Result ([ordered]@{ action = $Action; status = 'ok'; target = (Get-ElementInfo $target.element); inputMode = 'uia-pattern' })
    }
}
