# Save the clipboard image (e.g. from Win+Shift+S) to a PNG and type its path
# into the focused Herdr pane, so Claude Code / Codex can read the screenshot.
# Bound in Herdr config.toml to prefix+i (and prefix+ш for the Russian layout).
Add-Type -AssemblyName System.Windows.Forms, System.Drawing

$pane = ((herdr pane list | ConvertFrom-Json).result.panes | Where-Object { $_.focused } | Select-Object -First 1).pane_id
if (-not $pane) { exit 0 }

$img = [System.Windows.Forms.Clipboard]::GetImage()
if (-not $img) {
    herdr notification show "No image in clipboard" --body "Take a screenshot with Win+Shift+S first" | Out-Null
    exit 0
}

$dir = Join-Path $env:TEMP 'claude\shots'
New-Item -ItemType Directory -Force $dir | Out-Null
$file = Join-Path $dir ("shot-{0:yyyyMMdd-HHmmss}.png" -f (Get-Date))
$img.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
$img.Dispose()

herdr pane send-text $pane "$file " | Out-Null
