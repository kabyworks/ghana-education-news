# Register a task that refreshes the phone copy every 30 minutes while this user is logged on.
$ErrorActionPreference = "Stop"
$Script = Join-Path $PSScriptRoot "refresh.ps1"
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "Ghana Education News refresh" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Fetch education feeds and refresh the phone copy while this PC is on." -Force | Out-Null
Write-Output "Scheduled task ready: Ghana Education News refresh"
