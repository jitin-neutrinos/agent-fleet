# install.ps1 - agent-fleet orchestrator, Windows edition (no WSL / Git Bash needed).
# One-liner:  irm https://harness.jitinnair.com/install.ps1 | iex
# Mirrors install.sh (bash). Targets Windows PowerShell 5.1+ (no PS7-only syntax).
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'

# ---------- banner ------------------------------------------------------------
$ESC = [char]27
$B = "$ESC[38;5;33m"; $BB = "$ESC[1;38;5;33m"; $G = "$ESC[38;5;46m"
$R = "$ESC[38;5;203m"; $D = "$ESC[90m"; $X = "$ESC[0m"
function Write-Step($m) { Write-Host "  $B>$X $D$m$X" }
function Write-Ok($m)   { Write-Host "  $G OK $X $m" }
function Die($m)        { Write-Host "$R[af:error]$X $m"; exit 1 }
# UTF-8 without BOM (PS5.1 Set-Content -Encoding utf8 adds a BOM that breaks node JSON.parse)
function Write-Utf8NoBom([string]$Path, [string]$Text) {
  [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

Write-Host ''
Write-Host "$BB  agent-fleet $X $D one fleet - every harness (windows) $X"
Write-Host "  $D skills / plugins / MCPs / sync / repair $X"
Write-Host ''

# ---------- 0. prerequisites ---------------------------------------------------
if ($PSVersionTable.PSVersion.Major -lt 5) { Die "PowerShell 5+ required (you have $($PSVersionTable.PSVersion))." }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Die "git is required. Install it first:  winget install --id Git.Git -e"
}
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Write-Host "  $R!$X claude not found - Claude Code is the main consumer of the fleet."
  Write-Host "        Install it first:  ${B}irm https://claude.ai/install.ps1 | iex$X"
  $ans = Read-Host "        Continue anyway (installs skills+MCP defs for later)? [y/N]"
  if ($ans -notmatch '^[Yy]') { Die "install claude first, then re-run this installer." }
}

# ---------- 1. locate repo ------------------------------------------------------
$HomeRoot = if ($HomeRoot) { $HomeRoot } else { $HOME }
$AFDir = if ($env:AF_DIR) { $env:AF_DIR } else { Join-Path $HomeRoot 'agent-fleet' }
$RepoUrl = if ($env:AF_REPO_URL) { $env:AF_REPO_URL } else { 'jitin-neutrinos/agent-fleet' }
$RepoHttps = "https://github.com/$RepoUrl.git"

# a pre-seeded dir without .git is moved aside, same policy as install.sh
if ((Test-Path $AFDir) -and -not (Test-Path (Join-Path $AFDir '.git')) -and
    (Get-ChildItem $AFDir -Force -ErrorAction SilentlyContinue | Select-Object -First 1)) {
  $bak = "$AFDir.bak.$(Get-Date -Format yyyyMMddHHmmss)"
  Move-Item $AFDir $bak
  Write-Step "existing non-git copy moved aside (kept as $bak)"
}

if (Test-Path (Join-Path $AFDir '.git')) {
  Write-Step "repo exists at $AFDir - pulling"
  Push-Location $AFDir
  git -c credential.interactive=never pull --ff-only 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { Write-Ok 'repo up to date' } else { Write-Step 'repo pull skipped - continuing with existing copy' }
  Pop-Location
} else {
  Write-Step "cloning $RepoUrl -> $AFDir"
  git clone --depth 1 $RepoHttps $AFDir 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Step 'anonymous clone failed - retrying with your GitHub credentials'
    git clone $RepoHttps $AFDir
    if ($LASTEXITCODE -ne 0) { Die "clone failed - check access to $RepoUrl" }
  }
  Write-Ok 'cloned'
}

# ---------- 2. detect harnesses (windows-native) --------------------------------
Write-Host ''
Write-Host "$BB  Harnesses on this machine$X"
Write-Host '  ------------------------------------------------------'
$Detected = @()
function Ver([string]$c) { try { (& $c --version 2>$null | Select-Object -First 1) } catch { '-' } }
if (Get-Command claude -ErrorAction SilentlyContinue)   { $Detected += 'claude';      Write-Host "  $G*$X claude $(Ver claude)" }
if (Get-Command opencode -ErrorAction SilentlyContinue) { $Detected += 'opencode';    Write-Host "  $G*$X opencode $(Ver opencode)" }
if (Get-Command gemini -ErrorAction SilentlyContinue)   { $Detected += 'gemini';      Write-Host "  $G*$X gemini $(Ver gemini)" }
if (Get-Command agy -ErrorAction SilentlyContinue)      { $Detected += 'antigravity'; Write-Host "  $G*$X antigravity $(Ver agy)" }
# hermes is Linux-only today; skipped on windows
if (-not $Detected) { Die 'no harnesses detected (claude/opencode/gemini/antigravity)' }

# ---------- 3. install skills (flat depth-1 dirs) --------------------------------
$SkillsSrc = Join-Path $AFDir 'skills'
function Get-FlatSkills {
  # store keeps skills categorised (skills/<cat>/<name>/SKILL.md); harnesses read
  # flat <skills-root>/<name>/SKILL.md -> stage a flat copy (same as claude.sh/antigravity.sh)
  # NOTE: no 'yield' - it is PowerShell 7+ only and this must run on 5.1
  $out = @(); $seen = @{}
  foreach ($cat in Get-ChildItem $SkillsSrc -Directory) {
    if (Test-Path (Join-Path $cat.FullName 'SKILL.md')) { $out += $cat }
    foreach ($sub in Get-ChildItem $cat.FullName -Directory -ErrorAction SilentlyContinue) {
      if ((Test-Path (Join-Path $sub.FullName 'SKILL.md')) -and -not $seen.ContainsKey($sub.Name)) {
        $seen[$sub.Name] = $true; $out += $sub
      }
    }
  }
  return ,$out
}
function Install-FlatSkills([string]$DestRoot) {
  New-Item -ItemType Directory -Force -Path $DestRoot | Out-Null
  $n = 0
  # @( ) unwraps Get-FlatSkills' returned array correctly on PS5.1 (bare foreach
  # over a pipeline-callled fn sees ONE object: the wrapped array itself)
  $skills = @($(Get-FlatSkills))
  if ($skills.Count -eq 1 -and $skills[0] -is [System.Array]) { $skills = @($skills[0]) }
  foreach ($s in $skills) {
    $dst = Join-Path $DestRoot $s.Name
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    Copy-Item $s.FullName $dst -Recurse -Force
    $n++
  }
  return $n
}

if ($Detected -contains 'claude') {
  $n = Install-FlatSkills (Join-Path $HomeRoot '.claude\skills')
  Write-Ok "skills -> ~\.claude\skills ($n skills)"
}
if ($Detected -contains 'opencode') {
  $n = Install-FlatSkills (Join-Path $HomeRoot '.config\opencode\skills')
  Write-Ok "skills -> ~\.config\opencode\skills ($n skills)"
}
if ($Detected -contains 'antigravity') {
  $n1 = Install-FlatSkills (Join-Path $HomeRoot '.gemini\config\skills')
  $n2 = Install-FlatSkills (Join-Path $HomeRoot '.gemini\antigravity\global_skills')
  Write-Ok "skills -> ~\.gemini\config\skills + global_skills ($n1/$n2)"
}

# ---------- 4. MCPs ----------------------------------------------------------------
# claude.list rows: name|kind|spec|args(space-separated)|ENV_NAMES|notes
# Skipped by design on windows: env-gated rows (no key hoovering on a fresh box),
# MACHINE_LOCAL rows (kurama-core binaries), http rows pointed at 127.0.0.1
# (kurama-core-local services: laya, openviking, graphify).
$ClaudeListPath = Join-Path $AFDir 'mcp\claude.list'
if ($Detected -contains 'claude' -and (Test-Path $ClaudeListPath)) {
  foreach ($line in Get-Content $ClaudeListPath) {
    if ($line -notmatch '^[a-z]') { continue }
    $p = $line -split '\|'
    $name=$p[0]; $kind=$p[1]; $spec=$p[2]; $argsStr=$p[3]; $envKeys=$p[4]
    if (-not $envKeys) { $envKeys = '' } else { $envKeys = $envKeys.Trim() }
    if ($envKeys -and $envKeys -ne '-') { continue }              # needs a key we do not have
    if ($kind -eq 'http') {
      if ($spec -like '*127.0.0.1*' -or $spec -like '*localhost*' -or $spec -like '``$*') { continue }
      & claude mcp add --scope user --transport http $name $spec 2>$null | Out-Null
      Write-Host "  $D+ $name (claude, http)$X"
    }
    elseif ($spec -like 'MACHINE_LOCAL:*') { continue }           # desktop-only binaries
    else {
      if ($spec -eq 'docker') {
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { continue }
        $bin = 'docker'
        $argv = @(($argsStr -split ' ') | Where-Object { $_ -and $_ -ne '[]' -and $_ -ne '-' })
      } else {
        $bin = ($spec -split ' ')[0]
        if ($bin -match '^/' -or $bin -match '^~') { continue }   # unix-abs binary -> not for windows
        if (-not (Get-Command $bin -ErrorAction SilentlyContinue)) { continue }  # npx/uvx absent
        $argv = @(($spec -split ' ' | Select-Object -Skip 1) | Where-Object { $_ }) +
                @(($argsStr -split ' ') | Where-Object { $_ -and $_ -ne '[]' -and $_ -ne '-' })
      }
      $argv = @($argv | Where-Object { $_ })
      & claude mcp add --scope user $name -- $bin @argv 2>$null | Out-Null
      Write-Host "  $D+ $name (claude, stdio -> $bin)$X"
    }
  }
  Write-Ok 'claude MCP defs synced'
}

# marketplace plugins (same two the linux claude leg installs)
if ($Detected -contains 'claude') {
  & claude plugin marketplace add $RepoUrl 2>$null | Out-Null
  foreach ($plug in @('ponytail','caveman')) {
    & claude plugin install "$plug@agent-fleet" --scope user 2>$null | Out-Null
  }
  Write-Ok 'marketplace plugins (ponytail, caveman)'
}

$OcJson = Join-Path $HomeRoot '.config\opencode\opencode.json'
if ($Detected -contains 'opencode') {
  New-Item -ItemType Directory -Force -Path (Split-Path $OcJson) | Out-Null
  $oc = if ((Test-Path $OcJson) -and (Get-Item $OcJson).Length -gt 0) { Get-Content $OcJson -Raw | ConvertFrom-Json } else { New-Object PSObject }
  $fleet = Get-Content (Join-Path $AFDir 'mcp\opencode.json') -Raw | ConvertFrom-Json
  if (-not $oc.PSObject.Properties['mcp']) { $oc | Add-Member -NotePropertyName mcp -NotePropertyValue (New-Object PSObject) }
  foreach ($prop in $fleet.PSObject.Properties) {
    if (-not $oc.mcp.PSObject.Properties[$prop.Name]) {
      $oc.mcp | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value
    }
  }
  Write-Utf8NoBom $OcJson ($oc | ConvertTo-Json -Depth 20)
  Write-Ok 'opencode mcp block merged -> ~\.config\opencode\opencode.json'
}

$GmJson = Join-Path $HomeRoot '.gemini\settings.json'
if ($Detected -contains 'gemini') {
  New-Item -ItemType Directory -Force -Path (Split-Path $GmJson) | Out-Null
  $gm = if ((Test-Path $GmJson) -and (Get-Item $GmJson).Length -gt 0) { Get-Content $GmJson -Raw | ConvertFrom-Json } else { New-Object PSObject }
  $fleet = (Get-Content (Join-Path $AFDir 'mcp\gemini.json') -Raw | ConvertFrom-Json).mcpServers
  if (-not $gm.PSObject.Properties['mcpServers']) { $gm | Add-Member -NotePropertyName mcpServers -NotePropertyValue (New-Object PSObject) }
  foreach ($prop in $fleet.PSObject.Properties) {
    if (-not $gm.mcpServers.PSObject.Properties[$prop.Name]) {
      $gm.mcpServers | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value
    }
  }
  Write-Utf8NoBom $GmJson ($gm | ConvertTo-Json -Depth 20)
  Write-Ok 'gemini mcpServers merged -> ~\.gemini\settings.json'
}

# ---------- 5. rulebook (tool-router mandate) ---------------------------------------
$Rulebook = Join-Path $HomeRoot 'AGENTS.md'
$Src = Get-Content (Join-Path $AFDir 'rules\tool-router-mandate.md') -Raw
if ((Test-Path $Rulebook) -and ((Get-Content $Rulebook -Raw) -match '<!-- tool-router:begin -->')) {
  $raw = Get-Content $Rulebook -Raw
  $new = [regex]::Replace($raw,
    '(?s)<!-- tool-router:begin -->.*?<!-- tool-router:end -->',
    ("<!-- tool-router:begin -->" + [Environment]::NewLine + $Src + "<!-- tool-router:end -->"))
  Write-Utf8NoBom $Rulebook $new
} else {
  $mark = "<!-- tool-router:begin -->" + [Environment]::NewLine + $Src + "<!-- tool-router:end -->" + [Environment]::NewLine
  if (Test-Path $Rulebook) {
    Write-Utf8NoBom $Rulebook ((Get-Content $Rulebook -Raw) + [Environment]::NewLine + $mark)
  } else {
    Write-Utf8NoBom $Rulebook $mark
  }
}
Write-Ok 'rulebook updated -> ~\AGENTS.md'

# ---------- 6. summary ---------------------------------------------------------------
Write-Host ''
Write-Host "$BB  Install complete$X"
Write-Host '  ------------------------------------------------------'
foreach ($d in $Detected) { Write-Ok $d }
Write-Host "  ${D}restart each harness to pick up skills/MCPs - re-run to repair$X"
Write-Host "  ${D}store: https://harness.jitinnair.com/$X"
Write-Host ''
