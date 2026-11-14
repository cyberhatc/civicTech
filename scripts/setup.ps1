<#
.SYNOPSIS
    Provision a clean development environment for JanVaani UP.

.DESCRIPTION
    Creates the Python virtual environment, installs the backend dependencies,
    installs the frontend npm packages, generates the PWA icons and seeds the
    SQLite database. Safe to run repeatedly.

.EXAMPLE
    .\scripts\setup.ps1
    .\scripts\setup.ps1 -SkipFrontend
#>
[CmdletBinding()]
param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Write-Step($message) {
    Write-Host "`n==> $message" -ForegroundColor Cyan
}

function Write-Ok($message) {
    Write-Host "    [OK] $message" -ForegroundColor Green
}

# --- 1. Python virtual environment ------------------------------------------
if (-not $SkipBackend) {
    Write-Step "Python environment"

    $venv = Join-Path $Root ".venv"
    $python = Join-Path $venv "Scripts\python.exe"

    if ($Force -and (Test-Path $venv)) {
        Write-Host "    removing existing .venv"
        Remove-Item $venv -Recurse -Force
    }

    if (-not (Test-Path $python)) {
        # `python` is a Windows Store stub on many machines - prefer the launcher.
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if ($launcher) {
            Write-Host "    creating venv with 'py -m venv'"
            & py -m venv $venv
        } else {
            Write-Host "    creating venv with 'python -m venv'"
            & python -m venv $venv
        }
    } else {
        Write-Host "    venv already present"
    }

    if (-not (Test-Path $python)) {
        throw "Could not create the virtual environment. Install Python 3.11+ and re-run."
    }
    Write-Ok "venv ready at .venv"

    Write-Step "Backend dependencies"
    & $python -m pip install --upgrade pip --quiet
    & $python -m pip install -r (Join-Path $Root "backend\requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    Write-Ok "backend requirements installed"

    Write-Step "Database seed"
    & $python -c "import sys; sys.path.insert(0, r'backend'); from app.db.database import get_db; from app.db.seed import seed; print(seed(get_db()))"
    if ($LASTEXITCODE -ne 0) { throw "seeding failed" }
    Write-Ok "database seeded"
}

# --- 2. Frontend -------------------------------------------------------------
if (-not $SkipFrontend) {
    Write-Step "Frontend dependencies"
    Push-Location (Join-Path $Root "frontend")
    try {
        if (-not (Test-Path "package.json")) { throw "frontend/package.json is missing" }
        npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
        Write-Ok "npm packages installed"
    } finally {
        Pop-Location
    }

    Write-Step "PWA icons"
    & $python (Join-Path $Root "scripts\make_icons.py")
    if ($LASTEXITCODE -ne 0) { throw "icon generation failed" }
    Write-Ok "icons generated in frontend/public"
}

# --- 3. .env -----------------------------------------------------------------
Write-Step "Environment file"
$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $Root ".env.example") $envFile
    Write-Ok ".env created from .env.example"
} else {
    Write-Host "    .env already exists - leaving it untouched"
}

Write-Host "`n==> Setup complete" -ForegroundColor Green
Write-Host "    Start both servers with:  .\scripts\dev.ps1" -ForegroundColor Green
Write-Host "    Add a GROQ_API_KEY to .env to enable the live LLM + Whisper." -ForegroundColor DarkGray
