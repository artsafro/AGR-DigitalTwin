# Get the latest changes for the focused tab's checkout (Ctrl+B Shift+M).
#   on main          -> git pull --ff-only from origin (no push, no rewrite)
#   on a task branch -> git merge main (share what other agents published)
# Refuses when the checkout has uncommitted changes or its agent is working;
# a conflicting merge is aborted. The result is shown as a Herdr notification.
param([string]$Pane)   # default: the focused pane
$ErrorActionPreference = 'Continue'

function Notify([string]$title, [string]$body) {
    herdr notification show $title --body $body | Out-Null
}

$panes = @((herdr pane list | ConvertFrom-Json).result.panes)
$focused = if ($Pane) { $panes | Where-Object { $_.pane_id -eq $Pane } }
           else { $panes | Where-Object { $_.focused } }
$focused = $focused | Select-Object -First 1
if (-not $focused) { exit 0 }

# The checkout is the AGENT pane's folder (feeds may run from elsewhere).
$agent = $panes | Where-Object { $_.tab_id -eq $focused.tab_id -and ($_.label -eq 'AGENT' -or $_.agent) } |
    Select-Object -First 1
$cwd = if ($agent) { $agent.cwd } else { $focused.cwd }
$repo = (git -C $cwd rev-parse --show-toplevel 2>$null)
if (-not $repo) { Notify 'Update skipped' "Not a git checkout: $cwd"; exit 0 }

if ($agent -and $agent.agent_status -eq 'working') {
    Notify 'Update skipped' "$($agent.agent) is working in this checkout; try when it is idle"; exit 0
}
if (git -C $repo status --porcelain --untracked-files=no) {
    Notify 'Update skipped' 'Uncommitted changes here; commit or stash them first'; exit 0
}

$branch = git -C $repo branch --show-current
if ($branch -eq 'main') {
    $out = git -C $repo pull --ff-only 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) { Notify 'main updated from GitHub' ($out.Trim() -split "`n")[-1] }
    else { Notify 'Pull failed (main)' ($out.Trim() -split "`n")[-1] }
    exit 0
}

$before = git -C $repo rev-parse HEAD
$out = git -C $repo merge --no-edit main 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    git -C $repo merge --abort 2>$null
    Notify "Merge of main into $branch aborted" 'Conflicts - resolve with the agent or the coordinator'
    exit 0
}
$count = git -C $repo rev-list --count "$before..HEAD"
Notify "$branch updated from main" "$count new commit(s) merged"
