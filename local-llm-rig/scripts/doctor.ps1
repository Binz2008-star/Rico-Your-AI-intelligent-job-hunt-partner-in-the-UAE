<#
.SYNOPSIS
    Health check for the local LLM rig. Run this after every Ollama update.

.DESCRIPTION
    The failure mode this exists to catch: an Ollama update ships a CUDA runtime that no
    longer supports Pascal (CUDA 13 dropped compute capability 6.1), the GTX 1060 silently
    stops being used, and everything quietly falls back to the CPU at a fraction of the
    speed. There is no error message when that happens -- only this check.

    Exits non-zero if the GPU is not actually being used for inference.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\doctor.ps1
#>

[CmdletBinding()]
param(
    [string]$Host_ = "http://127.0.0.1:11434"
)

$ErrorActionPreference = "Stop"
$problems = @()
$warnings = @()

function Write-Section($text) {
    Write-Host ""
    Write-Host "== $text" -ForegroundColor Cyan
}

function Write-Ok($text)   { Write-Host "  [ok]   $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "  [warn] $text" -ForegroundColor Yellow }
function Write-Bad($text)  { Write-Host "  [FAIL] $text" -ForegroundColor Red }

Write-Host "Local LLM rig health check" -ForegroundColor White

# --------------------------------------------------------------------------- Ollama
Write-Section "Ollama"

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Bad "ollama not found on PATH. Install from https://ollama.com/download"
    exit 1
}

$ollamaVersion = (& ollama --version 2>&1 | Out-String).Trim()
Write-Ok "installed: $ollamaVersion"
Write-Host "         (note this version -- if a future update breaks Pascal, reinstall it)" -ForegroundColor DarkGray

try {
    $null = Invoke-RestMethod -Uri "$Host_/api/version" -TimeoutSec 5
    Write-Ok "service responding at $Host_"
} catch {
    Write-Bad "service not responding at $Host_. Start Ollama from the Start menu."
    exit 1
}

# ------------------------------------------------------------------------------ GPU
Write-Section "GPU"

$haveSmi = [bool](Get-Command nvidia-smi -ErrorAction SilentlyContinue)
if (-not $haveSmi) {
    Write-Warn "nvidia-smi not found -- cannot verify the driver. Is the NVIDIA driver installed?"
    $warnings += "nvidia-smi missing"
} else {
    $query = & nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free `
                          --format=csv,noheader,nounits 2>&1
    $row = ($query | Select-Object -First 1) -split '\s*,\s*'
    if ($row.Count -ge 4) {
        $name      = $row[0]
        $driver    = $row[1]
        $totalMiB  = [int]$row[2]
        $freeMiB   = [int]$row[3]
        Write-Ok "$name (driver $driver)"
        Write-Ok ("VRAM: {0} MiB free of {1} MiB total" -f $freeMiB, $totalMiB)

        # Tier 2 needs roughly 5.2 GB (~5300 MiB) free to stay fully on the GPU.
        if ($freeMiB -lt 5300) {
            Write-Warn "less than 5300 MiB free -- hunter-open (5.0 GB) will likely spill to CPU."
            Write-Host "         Close the browser and anything else using the GPU." -ForegroundColor DarkGray
            $warnings += "low free VRAM"
        }
    } else {
        Write-Warn "could not parse nvidia-smi output"
        $warnings += "nvidia-smi unparseable"
    }
}

# -------------------------------------------------------------------- Env / settings
Write-Section "Settings"

$kv = [Environment]::GetEnvironmentVariable("OLLAMA_KV_CACHE_TYPE", "User")
if ($kv -eq "q8_0") {
    Write-Ok "OLLAMA_KV_CACHE_TYPE = q8_0"
} elseif ([string]::IsNullOrEmpty($kv)) {
    Write-Warn "OLLAMA_KV_CACHE_TYPE not set -- the KV cache will use f16 and waste VRAM."
    Write-Host "         Fix: run scripts\setup.ps1, or  setx OLLAMA_KV_CACHE_TYPE ""q8_0""" -ForegroundColor DarkGray
    $warnings += "KV cache not quantized"
} else {
    Write-Warn "OLLAMA_KV_CACHE_TYPE = $kv (expected q8_0)"
    $warnings += "unexpected KV cache type"
}

$fa = [Environment]::GetEnvironmentVariable("OLLAMA_FLASH_ATTENTION", "User")
$faShown = if ([string]::IsNullOrEmpty($fa)) { "<unset>" } else { $fa }
Write-Host "  [info] OLLAMA_FLASH_ATTENTION = $faShown" -ForegroundColor DarkGray
Write-Host "         Flash attention is not a guaranteed win on Pascal. Benchmark both." -ForegroundColor DarkGray

# ------------------------------------------------------------------------- Real test
Write-Section "Inference placement (the actual test)"

$tags = Invoke-RestMethod -Uri "$Host_/api/tags" -TimeoutSec 15
$installed = @($tags.models | ForEach-Object { $_.name })

if ($installed.Count -eq 0) {
    Write-Warn "no models installed -- cannot verify GPU is used. Run scripts\setup.ps1 first."
    $warnings += "no models installed"
} else {
    # Prefer a hunter-* model; otherwise just use whatever is smallest.
    $probe = $installed | Where-Object { $_ -like "hunter-open-fast*" } | Select-Object -First 1
    if (-not $probe) { $probe = $installed | Select-Object -First 1 }

    Write-Host "  loading $probe ..." -NoNewline
    $body = @{ model = $probe; prompt = "hi"; stream = $false;
               options = @{ num_predict = 1 } } | ConvertTo-Json -Depth 4
    try {
        $null = Invoke-RestMethod -Uri "$Host_/api/generate" -Method Post `
                                  -Body $body -ContentType "application/json" -TimeoutSec 600
        Write-Host " done"
    } catch {
        Write-Host ""
        Write-Bad "generation failed for ${probe}: $($_.Exception.Message)"
        $problems += "generation failed"
    }

    $ps = Invoke-RestMethod -Uri "$Host_/api/ps" -TimeoutSec 15
    $entry = $ps.models | Where-Object { $_.name -eq $probe } | Select-Object -First 1

    if (-not $entry) {
        Write-Warn "/api/ps reported nothing -- the model may have unloaded already."
        $warnings += "placement unknown"
    } elseif ($entry.size -gt 0) {
        $pct = [math]::Round(100.0 * $entry.size_vram / $entry.size, 1)
        if ($entry.size_vram -le 0) {
            Write-Bad "0% GPU -- inference is running entirely on the CPU."
            Write-Host "         This is the CUDA-13-dropped-Pascal failure mode." -ForegroundColor DarkGray
            Write-Host "         See docs\HARDWARE_NOTES.md. Reinstall the previous Ollama version." -ForegroundColor DarkGray
            $problems += "GPU not used at all"
        } elseif ($pct -lt 99.5) {
            Write-Warn "$pct% GPU -- some layers spilled to system RAM."
            Write-Host "         Expected for hunter-max. For any other model, lower num_ctx." -ForegroundColor DarkGray
            $warnings += "partial CPU offload on $probe"
        } else {
            Write-Ok "$pct% GPU -- the card is being used correctly."
        }
    }
}

# ---------------------------------------------------------------------------- Verdict
Write-Host ""
if ($problems.Count -gt 0) {
    Write-Host "FAILED: $($problems -join '; ')" -ForegroundColor Red
    Write-Host "See docs\TROUBLESHOOTING.md" -ForegroundColor DarkGray
    exit 1
}
if ($warnings.Count -gt 0) {
    Write-Host "OK with warnings: $($warnings -join '; ')" -ForegroundColor Yellow
    exit 0
}
Write-Host "All checks passed." -ForegroundColor Green
exit 0
