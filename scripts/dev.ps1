<#
.SYNOPSIS
    Run the JanVaani UP backend and frontend together.

.DESCRIPTION
    Starts the FastAPI backend on :8000 and the Vite dev server on :5173.
    Both are launched in this window's job; Ctrl+C stops them together.

.EXAMPLE
    .\scripts\dev.ps1
    .\scripts\dev.ps1 -BackendOnly
#>

[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "  [X] Virtualenv missing. Run .\scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}

$backend = $null
$frontend = $null

function Stop-Children {
    Write-Host ""
    Write-Host "  Stopping..." -ForegroundColor Cyan
    foreach ($job in @($frontend, $backend)) {
        if ($job -and -not $job.HasExited) {
            try { $job.Kill() } catch { }
        }
    }
}
trap { Stop-Children; break }

if (-not $FrontendOnly) {
    Write-Host "  Starting API on http://127.0.0.1:$BackendPort" -ForegroundColor Cyan
    $backend = Start-Process -FilePath $venvPython `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "$BackendPort", "--reload" `
        -WorkingDirectory $root -PassThru -NoNewWindow
}

if (-not $BackendOnly) {
    Write-Host "  Starting web app on http://localhost:$FrontendPort" -ForegroundColor Cyan
    $frontend = Start-Process -FilePath "npm.cmd" `
        -ArgumentList "run", "dev", "--", "--port", "$FrontendPort" `
        -WorkingDirectory (Join-Path $root "frontend") -PassThru -NoNewWindow
}

Write-Host ""
Write-Host "  Citizen app   ->  http://localhost:$FrontendPort" -ForegroundColor Green
Write-Host "  Officer view  ->  http://localhost:$FrontendPort/admin" -ForegroundColor Green
Write-Host "  API docs      ->  http://127.0.0.1:$BackendPort/docs" -ForegroundColor Green
Write-Host ""
Write-Host "  Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

while ($true) {
    Start-Sleep -Seconds 2
    if ($backend -and $backend.HasExited) { Write-Host "  [X] Backend exited." -ForegroundColor Red; break }
    if ($frontend -and $frontend.HasExited) { Write-Host "  [X] Frontend exited." -ForegroundColor Red; break }
}

Stop-Children
