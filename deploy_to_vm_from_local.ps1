param(
    [string]$VmHost = "192.168.202.35",
    [string]$VmUser = "judy",
    [string]$RemoteZipPath = "/home/judy/projector_web_deploy.zip",
    [string]$RemoteDeployScript = "/var/www/projector_project/deploy_projector.sh",
    [string]$PythonExe = "",
    [string]$IdentityFile = "",
    [switch]$SkipNewsUpdate,
    [switch]$OpenAfterDeploy,
    [string]$OpenUrl = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ZipPath = Join-Path $Root "projector_web_deploy.zip"

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
        & $python -3 (Join-Path $Root "news_collector.py") --days 7 --max-items 1000 --retention-days 370
    } else {
        & $python (Join-Path $Root "news_collector.py") --days 7 --max-items 1000 --retention-days 370
    }
}

Invoke-Step "Build deploy zip" {
    & (Join-Path $Root "build_deploy_zip.ps1")
    if (-not (Test-Path -LiteralPath $ZipPath)) {
        throw "Deploy zip was not created: $ZipPath"
    }
}

$sshTarget = "$VmUser@$VmHost"
$remoteZipTarget = "${sshTarget}:$RemoteZipPath"
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

Invoke-Step "Run VM deploy script" {
    $remoteCommand = "ZIP_PATH='$RemoteZipPath' bash '$RemoteDeployScript'"
    & ssh @sshOptions $sshTarget $remoteCommand
}

if ($OpenAfterDeploy) {
    $url = $OpenUrl
    if (-not $url) {
        $url = "http://$VmHost/index.html"
    }
    Start-Process $url
}

Write-Host ""
Write-Host "Deploy complete." -ForegroundColor Green
