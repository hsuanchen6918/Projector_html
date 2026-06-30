param(
    [string]$VmHost = "192.168.202.35",
    [string]$VmUser = "judy",
    [string]$TaskName = "ProjectorNewsLocalDeploy",
    [string]$DailyTime = "09:00",
    [string]$IdentityFile = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$DeployScript = Join-Path $Root "deploy_to_vm_from_local.ps1"

if (-not (Test-Path -LiteralPath $DeployScript)) {
    throw "Missing deploy script: $DeployScript"
}

$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$DeployScript`"",
    "-VmHost", $VmHost,
    "-VmUser", $VmUser
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
    -Description "Collect projector news locally, build zip, upload to VM, and deploy." `
    -Force | Out-Null

Write-Host "Scheduled task installed: $TaskName"
Write-Host "Daily time: $DailyTime"
Write-Host "VM: $VmUser@$VmHost"
Write-Host "Run once manually:"
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$DeployScript`" -VmHost $VmHost -VmUser $VmUser"
