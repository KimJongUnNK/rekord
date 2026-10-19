# REKORD in one line (Windows 10/11, PowerShell):
#   irm https://github.com/KimJongUnNK/rekord/releases/latest/download/install.ps1 | iex
# Installs REKORD for your user (no admin) into %LOCALAPPDATA%\Programs\REKORD, adds Start menu and desktop
# shortcuts and starts it - without the SmartScreen "Weitere Informationen -> Trotzdem ausfuehren" detour.
# Running it again updates REKORD; your recordings in %USERPROFILE%\Rekord stay.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Invoke-WebRequest is 10x faster without the progress bar
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$url = "https://github.com/KimJongUnNK/rekord/releases/latest/download/REKORD-Windows-x64.zip"
$dest = Join-Path $env:LOCALAPPDATA "Programs\REKORD"
$tmp = Join-Path $env:TEMP ("rekord-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    Write-Host "> Lade REKORD (ca. 200 MB) ..." -ForegroundColor DarkYellow
    Invoke-WebRequest -Uri $url -OutFile "$tmp\rekord.zip" -UseBasicParsing
    Write-Host "> Installiere nach $dest ..." -ForegroundColor DarkYellow
    # an update replaces REKORD: the running one quits first (never while it records) - every copy, old ones too
    try { Invoke-WebRequest -Method Post -Uri "http://127.0.0.1:8765/api/shutdown" -UseBasicParsing -TimeoutSec 5 | Out-Null }
    catch {
        if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 409) {
            throw "REKORD nimmt gerade auf - erst die Aufnahme beenden, dann diese Zeile nochmal."
        }
    }
    Start-Sleep -Seconds 1
    Get-Process REKORD -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 800
    Expand-Archive -Path "$tmp\rekord.zip" -DestinationPath $tmp -Force
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
    Move-Item -Path "$tmp\REKORD" -Destination $dest
    Get-ChildItem -Recurse $dest | Unblock-File  # in case the zip carried a download mark

    $exe = Join-Path $dest "REKORD.exe"
    $shell = New-Object -ComObject WScript.Shell
    foreach ($lnk in @((Join-Path ([Environment]::GetFolderPath("Programs")) "REKORD.lnk"),
                       (Join-Path ([Environment]::GetFolderPath("Desktop")) "REKORD.lnk"))) {
        $s = $shell.CreateShortcut($lnk)
        $s.TargetPath = $exe
        $s.WorkingDirectory = $dest
        $s.IconLocation = "$exe,0"
        $s.Description = "REKORD - Meetings aufnehmen, wer spricht, Protokoll"
        $s.Save()
    }
    Write-Host "OK REKORD ist installiert (Startmenue + Desktop) und startet jetzt." -ForegroundColor Green
    Write-Host "  Fragt Windows nach der Firewall: 'Private Netzwerke' anhaken -> Zugriff zulassen (fuers iPhone)."
    Start-Process $exe
}
finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
