#requires -version 5.1
<#
.SYNOPSIS
  Add this repository's bin/ directory to the user PATH so that
  tsorg / tstat / tsdel / tsren can be invoked from any directory.

.DESCRIPTION
  Idempotent: re-running never duplicates the entry. The current
  session PATH is updated too, so the commands work immediately.
  Pass -Uninstall to remove the entry again.

.EXAMPLE
  .\install.ps1
  .\install.ps1 -Uninstall

  If script execution is blocked by policy, run it through a bypass:
  powershell -ExecutionPolicy Bypass -File install.ps1
#>
[CmdletBinding()]
param(
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'

$bin = Join-Path $PSScriptRoot 'bin'
if (-not (Test-Path $bin)) {
    throw "bin directory not found: $bin"
}

$current = [Environment]::GetEnvironmentVariable('Path', 'User')
$parts = @($current -split ';' | Where-Object { $_ -ne '' })

if ($Uninstall) {
    if ($parts -contains $bin) {
        $remaining = $parts | Where-Object { $_ -ne $bin }
        [Environment]::SetEnvironmentVariable('Path', ($remaining -join ';'), 'User')
        Write-Host "removed from user PATH: $bin"
    } else {
        Write-Host "not on user PATH, nothing to do: $bin"
    }
    return
}

if ($parts -notcontains $bin) {
    $parts += $bin
    [Environment]::SetEnvironmentVariable('Path', ($parts -join ';'), 'User')
    Write-Host "added to user PATH: $bin"
} else {
    Write-Host "already on user PATH: $bin"
}

# Reflect the change in the running session as well.
if (($env:Path -split ';') -notcontains $bin) {
    $env:Path = $env:Path.TrimEnd(';') + ';' + $bin
}

# tstat / tsdel / tsren and the Windows-native tsorg need python on PATH.
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Warning 'python was not found on PATH. Install Python 3.9+ for the Windows-native commands.'
}

Write-Host 'done. Open a new shell (or use this one) and try: tsorg --dry-run'
