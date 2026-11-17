$ErrorActionPreference = "Stop"
$password = ConvertTo-SecureString $env:MACHINE_PASSWORD -AsPlainText -Force
Set-LocalUser -Name "runneradmin" -Password $password
Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -Value 0
Enable-NetFirewallRule -DisplayGroup "Remote Desktop"
Restart-Service TermService -Force
Write-Host "✅ Windows RDP Setup Complete."
