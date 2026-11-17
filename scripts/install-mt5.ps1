$ErrorActionPreference = "Stop"
Write-Host "Downloading FBS MT5..."
Invoke-WebRequest -Uri "https://download.mql5.com/cdn/web/fbs.markets.inc/mt5/fbs5setup.exe" -OutFile "$env:TEMP\fbs5setup.exe"
Write-Host "Installing FBS MT5 silently..."
Start-Process -FilePath "$env:TEMP\fbs5setup.exe" -ArgumentList "/auto" -Wait
Write-Host "✅ FBS MT5 Installation Complete."
