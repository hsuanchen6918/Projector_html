param(
    [string]$VmHost = "192.168.202.35",
    [string]$VmUser = "judy",
    [string]$RemoteZipPath = "/home/judy/projector_web_deploy.zip",
    [string]$RemoteDeployScript = "/home/judy/deploy_projector.sh",
    [string]$RemoteAppDir = "/var/www/projector_project",
    [string]$PythonExe = "",
    [string]$IdentityFile = "",
    [switch]$SkipNewsUpdate,
    [switch]$DailyFocusOnly,
    [switch]$FullProjectDeploy,
    [switch]$EnableVmNewsFetch,
    [switch]$EnableVmNewsCron,
    [switch]$OpenAfterDeploy,
    [string]$OpenUrl = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ZipPath = Join-Path $Root "projector_web_deploy.zip"
$DeployScriptPath = Join-Path $Root "deploy_projector.sh"
$DeployScope = if ($FullProjectDeploy) { "full" } else { "daily-focus" }

if ($DailyFocusOnly -and $FullProjectDeploy) {
    throw "Use either -DailyFocusOnly or -FullProjectDeploy, not both."
}

function Resolve-Python {
    param([string]$Preferred)

    if ($Preferred) {
        if (-not (Test-Path -LiteralPath $Preferred)) {
            throw "PythonExe not found: $Preferred"
        }
        return $Preferred
    }

    $venvCandidates = @(
        (Join-Path $Root ".venv\Scripts\python.exe"),
        (Join-Path $Root "venv\Scripts\python.exe")
    )
    foreach ($candidate in $venvCandidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return $py.Source
    }

    throw "No Python found. Install Python or pass -PythonExe C:\path\to\python.exe"
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing command '$Name'. Install Windows OpenSSH Client first."
    }
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Action
}

Require-Command "scp"
Require-Command "ssh"

Invoke-Step "Collect projector news locally" {
    if ($SkipNewsUpdate) {
        Write-Host "Skipped by -SkipNewsUpdate"
        return
    }

    $python = Resolve-Python -Preferred $PythonExe
    if ((Split-Path -Leaf $python) -ieq "py.exe") {
        & $python -3 (Join-Path $Root "news_collector.py") --days 7 --max-items 2000 --retention-days 370
    } else {
        & $python (Join-Path $Root "news_collector.py") --days 7 --max-items 2000 --retention-days 370
    }
}

Invoke-Step "Build deploy zip" {
    & (Join-Path $Root "build_deploy_zip.ps1") -DeployScope $DeployScope
    if (-not (Test-Path -LiteralPath $ZipPath)) {
        throw "Deploy zip was not created: $ZipPath"
    }
    if (-not (Test-Path -LiteralPath $DeployScriptPath)) {
        throw "Deploy script was not found: $DeployScriptPath"
    }
}

$sshTarget = "$VmUser@$VmHost"
$remoteZipTarget = "${sshTarget}:$RemoteZipPath"
$remoteDeployTarget = "${sshTarget}:$RemoteDeployScript"
$sshOptions = @()
if ($IdentityFile) {
    if (-not (Test-Path -LiteralPath $IdentityFile)) {
        throw "IdentityFile not found: $IdentityFile"
    }
    $sshOptions += @("-i", $IdentityFile)
}

Invoke-Step "Upload zip to VM" {
    & scp @sshOptions $ZipPath $remoteZipTarget
}

Invoke-Step "Upload latest deploy script to VM" {
    & scp @sshOptions $DeployScriptPath $remoteDeployTarget
}

Invoke-Step "Run VM deploy script" {
    $vmNewsFetch = if ($EnableVmNewsFetch) { "1" } else { "0" }
    $vmNewsCron = if ($EnableVmNewsCron) { "1" } else { "0" }
    $remoteCommand = "sed -i 's/\r$//' '$RemoteDeployScript' && chmod +x '$RemoteDeployScript' && sudo -v && ZIP_PATH='$RemoteZipPath' APP_DIR='$RemoteAppDir' DEPLOY_SCOPE='$DeployScope' ENABLE_VM_NEWS_FETCH='$vmNewsFetch' ENABLE_VM_NEWS_CRON='$vmNewsCron' bash '$RemoteDeployScript'"
    & ssh -tt @sshOptions $sshTarget $remoteCommand
    if ($LASTEXITCODE -ne 0) {
        throw "VM deploy script failed with exit code $LASTEXITCODE"
    }
}

if ($OpenAfterDeploy) {
    $url = $OpenUrl
    if (-not $url) {
        $url = "http://$VmHost/index.html"
    }
    Start-Process $url
}

Write-Host ""
Write-Host "Deploy scope: $DeployScope" -ForegroundColor Green
Write-Host "Deploy complete." -ForegroundColor Green
