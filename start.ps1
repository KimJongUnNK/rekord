# REKORD starten (Windows). Rechtsklick → "Mit PowerShell ausführen".
# Erster Start richtet alles ein. Python fehlt?  winget install -e --id Python.Python.3.12
# Fürs iPhone im WLAN:  .\start.ps1 --host 0.0.0.0
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv")) {
    Write-Host "-> Richte REKORD ein ..."
    $py = (Get-Command py -ErrorAction SilentlyContinue)
    if ($py) { py -3 -m venv .venv } else { python -m venv .venv }
    .\.venv\Scripts\python.exe -m pip install -q --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -q -e ".[all]"
}
.\.venv\Scripts\python.exe -m rekord serve @args
