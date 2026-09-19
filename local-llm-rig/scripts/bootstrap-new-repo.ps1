<#
.SYNOPSIS
    Turn this folder into its own standalone git repository.

.DESCRIPTION
    This kit is delivered inside another repository for convenience. Run this once to
    extract it into a clean, independent repo with its own history, then push it to a
    new GitHub repository you create.

    It copies -- it does not move or delete anything from the source repo.

.PARAMETER Destination
    Where to create the standalone repo. Default: a sibling folder named
    ollama-uncensored-lab.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-new-repo.ps1
#>

[CmdletBinding()]
param(
    [string]$Destination
)

$ErrorActionPreference = "Stop"

$source = Split-Path -Parent $PSScriptRoot
if (-not $Destination) {
    $Destination = Join-Path (Split-Path -Parent $source) "ollama-uncensored-lab"
}

if (Test-Path $Destination) {
    Write-Host "$Destination already exists. Pick another path with -Destination." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "git not found on PATH." -ForegroundColor Red
    exit 1
}

Write-Host "Copying $source -> $Destination"
New-Item -ItemType Directory -Path $Destination | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $Destination -Recurse -Force

# Don't carry the extraction script itself into the standalone repo.
Remove-Item (Join-Path $Destination "scripts\bootstrap-new-repo.ps1") -ErrorAction SilentlyContinue

Push-Location $Destination
try {
    & git init -b main
    & git add -A
    & git commit -m "Initial commit: uncensored local LLM rig for GTX 1060 6GB"
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Standalone repo created at $Destination" -ForegroundColor Green
Write-Host ""
Write-Host "To publish it:" -ForegroundColor White
Write-Host "  1. Create an empty repo on GitHub (no README, no .gitignore)."
Write-Host "  2. Then:"
Write-Host "       cd `"$Destination`"" -ForegroundColor DarkGray
Write-Host "       git remote add origin https://github.com/<you>/ollama-uncensored-lab.git" -ForegroundColor DarkGray
Write-Host "       git push -u origin main" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Or, with the GitHub CLI, in one step:"
Write-Host "       gh repo create ollama-uncensored-lab --private --source . --push" -ForegroundColor DarkGray
