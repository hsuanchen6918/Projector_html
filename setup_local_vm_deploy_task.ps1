param(
    [string]$VmHost = "192.168.202.35",
    [string]$VmUser = "judy",
    [string]$TaskName = "ProjectorNewsLocalDeploy",
    [string]$DailyTime = "09:00",
    [string]$RemoteAppDir = "/var/www/projector_project",
    [string]$IdentityFile = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskRunner = Join-Path $Root "run_local_news_vm_deploy_task.ps1"

if (-not (Test-Path -LiteralPath $TaskRunner)) {
    throw "Missing task runner: $TaskRunner"
}

$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$TaskRunner`"",
    "-VmHost", $VmHost,
    "-VmUser", $VmUser,
    "-RemoteAppDir", $RemoteAppDir
)

if ($IdentityFile) {
    $arguments += @("-IdentityFile", "`"$IdentityFile`"")
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($arguments -join " ")
$trigger = New-ScheduledTaskTrigger -Daily -At $DailyTime
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Collect projector news locally, upload Daily Focus files to VM, and deploy without deleting VM-only projector data." `
    -Force | Out-Null

Write-Host "Scheduled task installed: $TaskName"
Write-Host "Daily time: $DailyTime"
Write-Host "VM: $VmUser@$VmHost"
Write-Host "Remote app dir: $RemoteAppDir"
Write-Host "Run once manually:"
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$TaskRunner`" -VmHost $VmHost -VmUser $VmUser -RemoteAppDir $RemoteAppDir"
