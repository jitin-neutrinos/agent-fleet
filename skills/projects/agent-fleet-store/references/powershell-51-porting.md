# PowerShell 5.1 porting (bash → .ps1) — validated headless

Probe harness — run real PowerShell in Docker (works on the Linux host, no WSL):

```bash
docker run --rm -v <dir>:/src mcr.microsoft.com/powershell:latest pwsh -NoProfile -Command "..."
```

The image ENTRYPOINT is not pwsh: `docker run … -NoProfile` alone fails exec —
always lead with `pwsh`.

Parse check (fast):

```pwsh
$e=$null
[void][System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$null, [ref]$e)
$e | ForEach-Object { Write-Host $_.Message }
```

**Parse-only is not verification.** All runtime traps below are invisible at
parse time. Validate logic for real: use the Parser AST to find
`FunctionDefinitionAst` nodes, splice their `.Extent.Text` with
`Invoke-Expression`, then call them against the REAL source tree mounted into
the container. A 548-skill staging port parses clean and still stages 0 skills
without this (the array-unwrapping trap).

## 5.1 traps (general rules — each bit once)

- **No `yield`.** PS 5.1 treats it as an unknown cmdlet; a generator rewritten
  with it silently emits 0 items. Accumulate `$out += $item`; `return ,$out`.
- **Array return + foreach.** `foreach ($x in Get-Fn)` sees ONE object (the
  returned array itself), not its elements. Capture `$items = @($(Get-Fn))` and
  unwrap once: `if ($items.Count -eq 1 -and $items[0] -is [System.Array])
  { $items = @($items[0]) }`.
- **`${var}` before `:`.** In `"$Dstore: text"` PS prefers variable `$Dstore`
  and errors on the colon; `"$Drestart"` silently reads an UNDEFINED
  `$Drestart`. Bracket every short variable followed by text:
  `"${D}store: …"`, `"${B}irm …"`.
- **BOM-free writes.** PS5.1 `Set-Content -Encoding utf8` prepends a BOM → a
  node JSON.parse on the written file dies transpiling it. Use
  `[System.IO.File]::WriteAllText($path, $text,
  (New-Object System.Text.UTF8Encoding($false)))`.
- **`$env:USERPROFILE` unset when pwsh runs on non-Windows** (docker probe, CI).
  Fall back: `$home = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }`
  and use that everywhere.
- **`curl` is an alias** (Invoke-WebRequest) on 5.1 — a bash-style `curl |`
  one-liner gets the WRONG object type; use `curl.exe` or explicit
  `Invoke-RestMethod`.

Colour: `[char]27` escape sequences only — `` `e `` is PS7-only.
