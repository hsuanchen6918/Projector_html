param(
    [string]$VmHost = "192.168.202.35",
    [string]$VmUser = "judy",
    [string]$RemoteAppDir = "/var/www/projector_project",
    [string]$IdentityFile = "",
    [switch]$SkipMedia,
    [switch]$SkipManifestUpdate,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$sshTarget = "$VmUser@$VmHost"
$sshOptions = @()

if ($IdentityFile) {
    if (-not (Test-Path -LiteralPath $IdentityFile)) {
        throw "IdentityFile not found: $IdentityFile"
    }
    $sshOptions += @("-i", $IdentityFile)
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

function Invoke-Native {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    if ($DryRun) {
        Write-Host ("DRY RUN: {0} {1}" -f $Command, ($Arguments -join " "))
        return @()
    }

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE"
    }
}

Require-Command "ssh"
Require-Command "scp"

Invoke-Step "Verify VM project folder" {
    Invoke-Native "ssh" (@($sshOptions) + @($sshTarget, "test -d '$RemoteAppDir'"))
}

Invoke-Step "Download projector data JSON files" {
    $listCommand = "cd '$RemoteAppDir' && find . -maxdepth 1 -type f -name 'data_*.json' -printf '%f\n'"

    if ($DryRun) {
        Write-Host "DRY RUN: ssh $sshTarget $listCommand"
        return
    }

    $dataFiles = & ssh @sshOptions $sshTarget $listCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to list data_*.json from VM"
    }
    $dataFiles = @($dataFiles | Where-Object { $_ -and $_.Trim() })
    if (-not $dataFiles.Count) {
        throw "No data_*.json files found in $RemoteAppDir"
    }

    foreach ($filename in $dataFiles) {
        $remoteFile = "${sshTarget}:$RemoteAppDir/$filename"
        Invoke-Native "scp" (@($sshOptions) + @($remoteFile, $Root))
    }
    Write-Host "Downloaded $($dataFiles.Count) data JSON files."
}

if (-not $SkipMedia) {
    foreach ($folder in @("images", "pptx")) {
        Invoke-Step "Download $folder folder" {
            $localFolder = Join-Path $Root $folder
            if (-not (Test-Path -LiteralPath $localFolder)) {
                New-Item -ItemType Directory -Path $localFolder | Out-Null
            }

            $remoteFolder = "${sshTarget}:$RemoteAppDir/$folder/."
            Invoke-Native "scp" (@($sshOptions) + @("-r", $remoteFolder, $localFolder))
        }
    }
}

if (-not $SkipManifestUpdate) {
    Invoke-Step "Update projector_data_manifest.json" {
        $buildScript = Join-Path $Root "build_deploy_zip.ps1"
        if (-not (Test-Path -LiteralPath $buildScript)) {
            throw "Missing build script: $buildScript"
        }

        if ($DryRun) {
            Write-Host "DRY RUN: powershell -ExecutionPolicy Bypass -File $buildScript -DeployScope daily-focus"
        } else {
            & powershell -ExecutionPolicy Bypass -File $buildScript -DeployScope daily-focus
            if ($LASTEXITCODE -ne 0) {
                throw "Manifest update failed with exit code $LASTEXITCODE"
            }
        }
    }
}

Write-Host ""
Write-Host "VM sync complete. Review changes, then commit/push if correct:" -ForegroundColor Green
Write-Host "  git status"
Write-Host "  git add data_*.json images pptx projector_data_manifest.json"
Write-Host "  git commit -m `"Sync projector data and media from VM`""
Write-Host "  git push origin main"
