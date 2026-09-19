<#
.SYNOPSIS
    Pull the uncensored base models and build the tuned hunter-* variants.

.DESCRIPTION
    Sets the VRAM-critical environment variables, pulls the base models, and builds the
    Modelfiles in modelfiles\ into named models you can run directly.

    Tier 3 (hunter-max) is a ~9 GB download that will not fit in VRAM. It is skipped by
    default -- pass -IncludeMax to install it.

.PARAMETER Tier
    Which tiers to install: 1, 2, or All. Default All (tiers 1 and 2).

.PARAMETER IncludeMax
    Also pull and build hunter-max (~9 GB, runs partly on CPU, single-digit tok/s).

.PARAMETER IncludeVision
    Also pull the uncensored vision model (3.3 GB).

.PARAMETER SkipEnv
    Don't touch environment variables.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -IncludeMax -IncludeVision
#>

[CmdletBinding()]
param(
    [ValidateSet("1", "2", "All")]
    [string]$Tier = "All",
    [switch]$IncludeMax,
    [switch]$IncludeVision,
    [switch]$SkipEnv
)

$ErrorActionPreference = "Stop"

$repoRoot     = Split-Path -Parent $PSScriptRoot
$modelfileDir = Join-Path $repoRoot "modelfiles"

function Write-Step($text) {
    Write-Host ""
    Write-Host "== $text" -ForegroundColor Cyan
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "ollama not found on PATH. Install it from https://ollama.com/download" -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------------- environment
if (-not $SkipEnv) {
    Write-Step "Environment"

    # The single most valuable setting on a 6 GB card: halves KV cache VRAM against f16,
    # which is often the difference between 100% GPU and a silent CPU spill.
    setx OLLAMA_KV_CACHE_TYPE "q8_0" | Out-Null
    Write-Host "  OLLAMA_KV_CACHE_TYPE = q8_0"

    # Deliberately NOT setting OLLAMA_FLASH_ATTENTION. On Pascal it is not a reliable
    # win -- benchmark it both ways. See docs\HARDWARE_NOTES.md.

    Write-Host ""
    Write-Host "  setx only affects processes started from now on." -ForegroundColor Yellow
    Write-Host "  Restart Ollama for this to take effect:" -ForegroundColor Yellow
    Write-Host "      Get-Process ollama* | Stop-Process -Force" -ForegroundColor DarkGray
    Write-Host "      # then relaunch Ollama from the Start menu" -ForegroundColor DarkGray
}

# ------------------------------------------------------------------------ models
# name -> base model to pull. The Modelfile of the same name is built on top.
$plan = [ordered]@{}

# Ordered by how de-restricted the model is, not by size.
#
# hunter-open and hunter-open-fast are JOSIEFIED builds: abliterated AND finetuned for
# openness. hunter-dolphin is an uncensored finetune on a different base (Llama 3.1),
# kept because refusals that survive abliteration are base-model-specific -- when one
# lineage balks, the other usually does not.

if ($Tier -eq "1" -or $Tier -eq "All") {
    $plan["hunter-open"]      = "goekdenizguelmez/JOSIEFIED-Qwen3:8b-q4_k_m"
    $plan["hunter-open-fast"] = "goekdenizguelmez/JOSIEFIED-Qwen3:4b-q4_k_m"
}
if ($Tier -eq "2" -or $Tier -eq "All") {
    $plan["hunter-dolphin"] = "huihui_ai/dolphin3-abliterated:8b"
}
if ($IncludeMax) {
    $plan["hunter-max"] = "huihui_ai/qwen3-abliterated:14b-v2-q4_K_M"
}

$failed = @()

foreach ($name in $plan.Keys) {
    $base = $plan[$name]
    Write-Step "$name  <-  $base"

    Write-Host "  pulling (resumable -- re-run this script if it stalls) ..."
    & ollama pull $base
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  pull failed. Tags move; check https://ollama.com/huihui_ai for the current one." -ForegroundColor Red
        $failed += $name
        continue
    }

    $modelfile = Join-Path $modelfileDir "$name.Modelfile"
    if (-not (Test-Path $modelfile)) {
        Write-Host "  missing $modelfile -- skipping build." -ForegroundColor Red
        $failed += $name
        continue
    }

    Write-Host "  building $name ..."
    & ollama create $name -f $modelfile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  build failed." -ForegroundColor Red
        $failed += $name
        continue
    }
    Write-Host "  ready: ollama run $name" -ForegroundColor Green
}

if ($IncludeVision) {
    Write-Step "vision model (used directly, no Modelfile)"
    & ollama pull huihui_ai/qwen3-vl-abliterated:4b
    if ($LASTEXITCODE -ne 0) { $failed += "qwen3-vl-abliterated:4b" }
}

# ------------------------------------------------------------------------ summary
Write-Step "Done"

if ($failed.Count -gt 0) {
    Write-Host "  failed: $($failed -join ', ')" -ForegroundColor Red
    Write-Host "  Model tags get re-pointed over time. Check the current tag list and" -ForegroundColor DarkGray
    Write-Host "  update modelfiles\<name>.Modelfile if a FROM line is stale." -ForegroundColor DarkGray
}

& ollama list

Write-Host ""
Write-Host "Next:" -ForegroundColor White
Write-Host "  1. Restart Ollama so OLLAMA_KV_CACHE_TYPE applies."
Write-Host "  2. powershell -ExecutionPolicy Bypass -File .\scripts\doctor.ps1"
Write-Host "  3. python .\scripts\bench.py --all           # speed"
Write-Host "  4. python .\scripts\refusal-probe.py --all   # how uncensored, measured"
Write-Host ""
if (-not $IncludeMax) {
    Write-Host "hunter-max (14B, ~9 GB, partly on CPU) was skipped. Add -IncludeMax to install it." -ForegroundColor DarkGray
}

exit $(if ($failed.Count -gt 0) { 1 } else { 0 })
