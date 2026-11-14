<#
.SYNOPSIS
    Run the JanVaani UP backend and frontend together.

.DESCRIPTION
    Starts the FastAPI server on :8000 and the Vite dev server on :5173, tails both
    logs to the console, and shuts both down cleanly on Ctrl+C.

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
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "No virtual environment found. Run .\scripts\setup.ps1 first."
}

$jobs = @()

try {
    if (-not $FrontendOnly) {
        Write-Host "==> Backend on http://127.0.0.1:$BackendPort" -ForegroundColor Cyan
        $jobs += Start-Job -Name "backend" -ScriptBlock {
            param($root, $port)
            Set-Location $root
            & (Join-Path $root ".venv\Scripts\python.exe") -m uvicorn app.main:app `
                --host 127.0.0.1 --port $port --app-dir backend
        } -ArgumentList $Root, $BackendPort
    }

    if (-not $BackendOnly) {
        Write-Host "==> Frontend on http://127.0.0.1:$FrontendPort" -ForegroundColor Cyan
        $jobs += Start-Job -Name "frontend" -ScriptBlock {
            param($dir, $port)
            Set-Location $dir
            npm run dev -- --port $port
        } -ArgumentList (Join-Path $Root "frontend"), $FrontendPort
    }

    Write-Host "`n    Citizen app : http://127.0.0.1:$FrontendPort" -ForegroundColor Green
    Write-Host "    Officer view: http://127.0.0.1:$FrontendPort/admin" -ForegroundColor Green
    Write-Host "    API docs    : http://127.0.0.1:$BackendPort/docs" -ForegroundColor Green
    Write-Host "`n    Press Ctrl+C to stop.`n" -ForegroundColor DarkGray

    while ($true) {
        Start-Sleep -Seconds 2
        foreach ($job in $jobs) {
            $output = Receive-Job $job -Keep 2>$null
            if ($output) { Write-Host $output -ForegroundColor DarkGray }
        }
    }
}
finally {
    Write-Host "`n==> Stopping..." -ForegroundColor Yellow
    $jobs | Stop-Job -ErrorAction SilentlyContinue
    $jobs | Remove-Job -Force -ErrorAction SilentlyContinue
}
