# Full UI refresh for every Herdr tab that holds an agent (Ctrl+B Shift+U).
# Reloads Herdr config, refreshes radar, restarts every feed (TOOLS / CHEAT / LOGS / HUD)
# on the current code, then runs layout.ps1 per tab to recreate missing panes.
# Agents are never stopped.
$ErrorActionPreference = 'Continue'

herdr server reload-config | Out-Null
herdr plugin action invoke hhdebb.herdr-radar.refresh 2>$null | Out-Null

$panes = @((herdr pane list | ConvertFrom-Json).result.panes)

# Stop feed processes so layout.ps1 restarts them on the current code (agents untouched).
foreach ($feed in ($panes | Where-Object { $_.label -in 'TOOLS', 'LOGS', 'CHEAT', 'HUD' })) {
    $shellPid = (herdr pane process-info --pane $feed.pane_id | ConvertFrom-Json).result.process_info.shell_pid
    if ($shellPid) {
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$shellPid" |
            Where-Object { $_.Name -match '^(py|python)\.exe$' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
}
Start-Sleep -Milliseconds 800

$tabs = $panes | Where-Object { $_.agent -or $_.label -eq 'AGENT' } | Group-Object tab_id
$fixed = 0
foreach ($tab in $tabs) {
    # Prefer the pane labelled AGENT; otherwise the pane running the agent.
    $agent = ($tab.Group | Where-Object { $_.label -eq 'AGENT' } | Select-Object -First 1)
    if (-not $agent) { $agent = $tab.Group | Where-Object { $_.agent } | Select-Object -First 1 }
    try {
        & "$PSScriptRoot\layout.ps1" -Pane $agent.pane_id
        $fixed++
    } catch {
        herdr notification show "Refresh failed in $($tab.Name)" --body "$_" | Out-Null
    }
}

herdr notification show "UI refreshed" --body "$fixed tab(s) checked: missing panels restored, idle feeds restarted" | Out-Null
