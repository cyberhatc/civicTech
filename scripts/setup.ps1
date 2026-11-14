<#
.SYNOPSIS
    One-command provisioning for JanVaani UP.

.DESCRIPTION
    Creates the Python virtualenv, installs backend + frontend dependencies,
    seeds the SQLite database and regenerates the PWA icons. Safe to re-run.

.EXAMPLE
    .\scripts\setup.ps1
#>

[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "  JanVaani UP - setup" -ForegroundColor Cyan
Write-Host "  ====================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Python virtualenv ----------------------------------------------------
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"

if ($Force -and (Test-Path $venv)) {
    Write-Host "  [!] Removing existing virtualenv" -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venv
}

if (-not (Test-Path $python)) {
    Write-Host "  [1/4] Creating virtualenv..." -ForegroundColor Cyan
    $created = $false
    foreach ($launcher in @("py", "python", "python3")) {
        if (Get-Command $launcher -ErrorAction SilentlyContinue) {
            & $launcher -m venv $venv
            if ($LASTEXITCODE -eq 0 -and (Test-Path $python)) { $created = $true; break }
        }
    }
    if (-not $created) {
        Write-Host "  [X] Could not create a virtualenv. Install Python 3.12+ and retry." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [1/4] Virtualenv already present" -ForegroundColor DarkGray
}

Write-Host "  [2/4] Installing backend dependencies..." -ForegroundColor Cyan
& $python -m pip install --upgrade pip --quiet
& $python -m pip install -r (Join-Path $root "backend\requirements.txt") --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [X] Backend dependency installation failed" -ForegroundColor Red
    exit 1
}

# --- 2. Frontend dependencies -------------------------------------------------
if (-not $SkipFrontend) {
    Write-Host "  [3/4] Installing frontend dependencies..." -ForegroundColor Cyan
    Push-Location (Join-Path $root "frontend")
    try {
        if (Get-Command npm -ErrorAction SilentlyContinue) {
            npm install --no-audit --no-fund --silent
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  [X] npm install failed" -ForegroundColor Red
                exit 1
            }
        } else {
            Write-Host "  [!] npm not found - skipping the frontend" -ForegroundColor Yellow
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "  [3/4] Skipping frontend" -ForegroundColor DarkGray
}

# --- 3. Seed the database -----------------------------------------------------
Write-Host "  [4/4] Seeding database and generating icons..." -ForegroundColor Cyan
Push-Location $root
try {
    & $python -c "import sys; sys.path.insert(0, 'backend'); from app.db.database import get_db; from app.db.seed import seed; print('  seeded:', seed(get_db()))"
    & $python (Join-Path $root "scripts\make_icons.py")
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "  Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "  Next:  .\scripts\dev.ps1" -ForegroundColor Cyan
Write-Host "    Citizen app   ->  http://localhost:5173"
Write-Host "    Officer view  ->  http://localhost:5173/admin"
Write-Host "    API docs      ->  http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "  Optional: copy .env.example to .env and add GROQ_API_KEY for live LLM + Whisper."
Write-Host ""
