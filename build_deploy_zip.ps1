param(
    [ValidateSet("full", "daily-focus")]
    [string]$DeployScope = "full"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ZipName = "projector_web_deploy.zip"
$ZipPath = Join-Path $Root $ZipName
$ExcludeFile = Join-Path $Root "deploy_exclude.txt"

if (-not (Test-Path -LiteralPath $ExcludeFile)) {
    throw "Missing deploy_exclude.txt"
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Convert-ToRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$FullPath
    )

    $baseUri = [Uri](([System.IO.Path]::GetFullPath($BasePath).TrimEnd('\') + '\'))
    $fileUri = [Uri]([System.IO.Path]::GetFullPath($FullPath))
    return [Uri]::UnescapeDataString($baseUri.MakeRelativeUri($fileUri).ToString())
}

function Test-Excluded {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string[]]$Patterns
    )

    $path = $RelativePath.Replace('\', '/')
    foreach ($pattern in $Patterns) {
        if ([string]::IsNullOrWhiteSpace($pattern)) { continue }
        $trimmed = $pattern.Trim()
        if ($trimmed.StartsWith("#")) { continue }

        if ($trimmed.EndsWith("/")) {
            $dirPattern = $trimmed.TrimEnd("/")
            if ($path -eq $dirPattern -or $path.StartsWith("$dirPattern/")) {
                return $true
            }
            continue
        }

        if ($path -like $trimmed -or (Split-Path -Leaf $path) -like $trimmed) {
            return $true
        }
    }
    return $false
}

function Update-ProjectorDataManifest {
    $manifestPath = Join-Path $Root "projector_data_manifest.json"
    $brands = Get-ChildItem -LiteralPath $Root -Filter "data_*.json" -File |
        ForEach-Object { $_.BaseName.Substring(5).ToLowerInvariant() } |
        Sort-Object -Unique

    $manifest = [ordered]@{
        brands = @($brands)
    }
    $manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
}

Update-ProjectorDataManifest

$patterns = Get-Content -LiteralPath $ExcludeFile -Encoding UTF8
$dailyFocusFiles = @(
    "index.html",
    "admin.html",
    "backend_server.py",
    "projector_data_manifest.json",
    "ai_client.py",
    "ai_engine.py",
    "news_collector.py",
    "news_sources.json",
    "news_data.json",
    "news.env.example",
    "NEWS_AUTOMATION.md",
    "LOCAL_VM_DEPLOY.md",
    "run_news_update.sh",
    "setup_news_cron.sh",
    "requirements.txt"
)

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

if ($DeployScope -eq "daily-focus") {
    $files = foreach ($relative in $dailyFocusFiles) {
        $fullPath = Join-Path $Root $relative
        if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
            Get-Item -LiteralPath $fullPath
        } else {
            Write-Warning "Daily Focus file not found and will be skipped: $relative"
        }
    }
} else {
    $files = Get-ChildItem -LiteralPath $Root -Recurse -File -Force | Where-Object {
        $relative = Convert-ToRelativePath -BasePath $Root -FullPath $_.FullName
        -not (Test-Excluded -RelativePath $relative -Patterns $patterns)
    }
}

$files = @($files | Sort-Object FullName -Unique)

$stream = [System.IO.File]::Open($ZipPath, [System.IO.FileMode]::CreateNew)
try {
    $archive = New-Object System.IO.Compression.ZipArchive($stream, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($file in $files) {
            $relative = Convert-ToRelativePath -BasePath $Root -FullPath $file.FullName
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $archive,
                $file.FullName,
                $relative,
                [System.IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
        }
    }
    finally {
        $archive.Dispose()
    }
}
finally {
    $stream.Dispose()
}

$result = Get-Item -LiteralPath $ZipPath
Write-Host "Created $($result.FullName)"
Write-Host "Size: $([math]::Round($result.Length / 1MB, 2)) MB"
Write-Host "Files: $($files.Count)"
Write-Host "Deploy scope: $DeployScope"
