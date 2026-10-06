# Toggle "commit large new files as links" (git config twin.linkLarge) for AGR-DigitalTwin.
# Bound in Herdr config.toml to prefix+shift+k (prefix+Л). State is shown in the HUD.
$repo = 'C:\Users\artsafro\AGR-DigitalTwin'
$on = (git -C $repo config --get twin.linkLarge) -ne 'false'
$new = if ($on) { 'false' } else { 'true' }
git -C $repo config twin.linkLarge $new
$mb = git -C $repo config --get twin.linkLargeMb
if (-not $mb) { $mb = 50 }
$title = if ($new -eq 'true') { "Big files: links ON (>$mb MB)" } else { 'Big files: links OFF' }
$body = if ($new -eq 'true') { 'New files over the limit are committed as links' } else { 'Large files will be committed (LFS)' }
herdr notification show $title --body $body | Out-Null
