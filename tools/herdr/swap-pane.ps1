# Swap the focused Herdr pane with its neighbour: swap-pane.ps1 left|right|up|down
# Bound to Ctrl+B Shift+arrows. Panels keep their labels, so refresh-all / layout
# repair respect the new arrangement.
param([Parameter(Mandatory)][ValidateSet('left', 'right', 'up', 'down')][string]$Direction)
$pane = ((herdr pane list | ConvertFrom-Json).result.panes | Where-Object { $_.focused } | Select-Object -First 1).pane_id
if ($pane) { herdr pane swap --pane $pane --direction $Direction | Out-Null }
