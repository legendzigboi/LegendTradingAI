$ErrorActionPreference = "Stop"
$password = ConvertTo-SecureString $env:MACHINE_PASSWORD -AsPlainText -Force

# Create the LegendAdmin user
$userExists = Get-LocalUser -Name "LegendAdmin" -ErrorAction SilentlyContinue
if (-not $userExists) {
    New-LocalUser -Name "LegendAdmin" -Password $password -FullName "Legend Admin" -Description "Legend Trading Bot"
    Add-LocalGroupMember -Group "Administrators" -Member "LegendAdmin"
    Write-Host "LegendAdmin user created."
} else {
    Set-LocalUser -Name "LegendAdmin" -Password $password
    Write-Host "LegendAdmin password updated."
}

# Enable RDP
Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -Value 0
Enable-NetFirewallRule -DisplayGroup "Remote Desktop"
Restart-Service TermService -Force
Write-Host "RDP Enabled."
