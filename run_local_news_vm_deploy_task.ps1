param(
    [string]$VmHost = "192.168.202.35",
    [string]$VmUser = "judy",
    [string]$RemoteAppDir = "/var/www/projector_project",
    [string]$IdentityFile = "",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$DeployScript = Join-Path $Root "deploy_to_vm_from_local.ps1"
$LogDir = Join-Path $Root "logs"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "local_news_vm_deploy_$Stamp.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Start-Transcript -Path $LogPath -Append | Out-Null

try {
    if (-not (Test-Path -LiteralPath $DeployScript)) {
        throw "Missing deploy script: $DeployScript"
    }

    $arguments = @(
        "-VmHost", $VmHost,
        "-VmUser", $VmUser,
        "-RemoteAppDir", $RemoteAppDir,
        "-DailyFocusOnly"
    )

    if ($IdentityFile) {
        $arguments += @("-IdentityFile", $IdentityFile)
    }
    if ($PythonExe) {
        $arguments += @("-PythonExe", $PythonExe)
    }

    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Start local news collect and VM deploy"
    & $DeployScript @arguments
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Deploy finished"
} catch {
    Write-Error $_
    exit 1
} finally {
    Stop-Transcript | Out-Null
}
