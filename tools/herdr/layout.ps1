# AGENT | TOOLS/CHEAT over LOGS | HUD for one Herdr tab.
# Idempotent repair: fill missing panels and restart only feeds whose pane is idle.
param([string]$Pane)
$ErrorActionPreference = 'Stop'

function Get-Panes {
    @((herdr pane list | ConvertFrom-Json).result.panes)
}

function Find-WorkspaceId($node) {
    if ($null -eq $node) { return $null }
    if ($node -is [string] -or $node -is [ValueType]) { return $null }
    foreach ($property in $node.PSObject.Properties) {
        if ($property.Name -eq 'workspace_id' -and $property.Value -is [string]) {
            return $property.Value
        }
        $found = Find-WorkspaceId $property.Value
        if ($found) { return $found }
    }
    return $null
}

function Get-Panel($panes, [string]$label) {
    $panes | Where-Object { $_.tab_id -eq $script:tabId -and $_.label -eq $label } |
        Select-Object -First 1
}

function New-Panel([string]$source, [string]$direction, [double]$ratio, [string]$label) {
    $result = herdr pane split $source --direction $direction --ratio $ratio | ConvertFrom-Json
    $id = $result.result.pane.pane_id
    if (-not $id) { throw "Could not create $label pane next to $source" }
    herdr pane rename $id $label | Out-Null
    $id
}

function Start-Panel([string]$paneId, [string]$command) {
    # On Windows Herdr reports only the pane's shell as foreground, so a running
    # feed is detected as a child process of that shell instead.
    $info = herdr pane process-info --pane $paneId | ConvertFrom-Json
    $shellPid = $info.result.process_info.shell_pid
    $children = @()
    if ($shellPid) {
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$shellPid" |
            Where-Object { $_.Name -notmatch '^(conhost|OpenConsole)\.exe$' })
    }
    if ($children.Count -eq 0) {
        herdr pane send-keys $paneId escape | Out-Null    # clear any half-typed line first
        herdr pane run $paneId $command | Out-Null
    }
}

$workspaceId = $null
if ($env:HERDR_PLUGIN_EVENT_JSON) {
    try {
        $event = $env:HERDR_PLUGIN_EVENT_JSON | ConvertFrom-Json
        $workspaceId = Find-WorkspaceId $event
    } catch {}
}

$panes = Get-Panes
if ($Pane) {
    $basis = $panes | Where-Object { $_.pane_id -eq $Pane } | Select-Object -First 1
} elseif ($workspaceId) {
    $basis = $panes | Where-Object { $_.workspace_id -eq $workspaceId } |
        Sort-Object { [int]($_.pane_id -replace '^.*:p', '') } | Select-Object -First 1
} else {
    $basis = $panes | Where-Object { $_.focused } | Select-Object -First 1
}
if (-not $basis) { exit 0 }
$script:tabId = $basis.tab_id
$panes = @($panes | Where-Object { $_.tab_id -eq $script:tabId })

$agent = $panes | Where-Object { $_.label -eq 'AGENT' } | Select-Object -First 1
if (-not $agent -and $Pane) {
    $agent = $basis
}
if (-not $agent) {
    $agent = $panes | Sort-Object { [int]($_.pane_id -replace '^.*:p', '') } |
        Select-Object -First 1
}
if (-not $agent) { exit 0 }

if ($agent.label -ne 'AGENT') {
    herdr pane rename $agent.pane_id AGENT | Out-Null
}
$agentId = $agent.pane_id

$logs = Get-Panel $panes 'LOGS'
$tools = Get-Panel $panes 'TOOLS'
if (-not $logs) {
    $logsId = New-Panel $agentId 'down' 0.68 'LOGS'
    $panes = Get-Panes | Where-Object { $_.tab_id -eq $script:tabId }
    $logs = Get-Panel $panes 'LOGS'
}
if (-not $tools) {
    $toolsId = New-Panel $agentId 'right' 0.62 'TOOLS'
    $panes = Get-Panes | Where-Object { $_.tab_id -eq $script:tabId }
    $tools = Get-Panel $panes 'TOOLS'
}
if (-not $logs -or -not $tools) { throw 'TOOLS/LOGS panel setup is incomplete' }

$cheat = Get-Panel $panes 'CHEAT'
if (-not $cheat) {
    New-Panel $tools.pane_id 'down' 0.5 'CHEAT' | Out-Null
    $panes = Get-Panes | Where-Object { $_.tab_id -eq $script:tabId }
    $cheat = Get-Panel $panes 'CHEAT'
}

$hud = Get-Panel $panes 'HUD'
if (-not $hud) {
    $hudId = New-Panel $logs.pane_id 'right' 0.6 'HUD'
    $panes = Get-Panes | Where-Object { $_.tab_id -eq $script:tabId }
    $hud = Get-Panel $panes 'HUD'
}

$feed = "py -3 `"$PSScriptRoot\agent_feed.py`" --pane $agentId"
Start-Panel $tools.pane_id "$feed --mode tools"
Start-Panel $logs.pane_id "$feed --mode logs"
if ($cheat) { Start-Panel $cheat.pane_id "py -3 `"$PSScriptRoot\cheat.py`"" }
if ($hud) { Start-Panel $hud.pane_id "py -3 `"$PSScriptRoot\hud.py`"" }
