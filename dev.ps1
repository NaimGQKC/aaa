# Windows PowerShell dev helper — mirrors the Makefile for Windows users.
#
# Usage (from the project folder):
#   powershell -ExecutionPolicy Bypass -File .\dev.ps1 setup
#   powershell -ExecutionPolicy Bypass -File .\dev.ps1 mistral-check
#   powershell -ExecutionPolicy Bypass -File .\dev.ps1 api
#   powershell -ExecutionPolicy Bypass -File .\dev.ps1 web
#
# Targets: setup | mistral-check | seed | api | web | test

param([Parameter(Position = 0)][string]$Target = "help")

$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"
$pip = ".\.venv\Scripts\pip.exe"
$env:PYTHONPATH = "api;packages/schemas;scripts"

switch ($Target) {
    "setup" {
        python -m venv .venv
        & $py -m pip install -q --upgrade pip
        & $pip install -e ./packages/schemas -e "./api[dev]"
        Write-Host "`nSetup done. Next: .\dev.ps1 mistral-check" -ForegroundColor Green
    }
    "mistral-check" { & $py scripts\mistral_check.py }
    "seed"          { & $py scripts\seed_demo.py }
    "api"           { & $py -m uvicorn app.main:app --app-dir api --reload --port 8000 }
    "web"           { Push-Location web; npm install; npm run dev; Pop-Location }
    "test"          { & $py -m pytest api\tests -q }
    default {
        Write-Host "Targets: setup | mistral-check | seed | api | web | test"
        Write-Host "Example: powershell -ExecutionPolicy Bypass -File .\dev.ps1 setup"
    }
}
