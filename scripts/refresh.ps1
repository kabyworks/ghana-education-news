# Fetch sources, then refresh the phone copy. An empty export leaves the previous copy in place.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$Log = Join-Path $Backend "data\refresh.log"
New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null

function Write-Log([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $Log -Value $line
}

Set-Location $Backend
& $Python -m app.ingestion
if ($LASTEXITCODE -ne 0) {
    Write-Log "Fetch failed. The phone copy was left unchanged."
    exit $LASTEXITCODE
}

& $Python -m app.publish
if ($LASTEXITCODE -ne 0) {
    Write-Log "Publish refused. The phone copy was left unchanged."
    exit $LASTEXITCODE
}

Set-Location $Root
git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Log "Published on this PC. This folder is not a git checkout, so nothing was pushed."
    exit 0
}
git remote get-url origin *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Log "Published on this PC. No origin remote is configured, so the phone cannot see a new copy yet."
    exit 0
}

git add -- docs
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Log "Phone copy unchanged."
    exit 0
}

git commit -m "Update the phone feed."
if ($LASTEXITCODE -ne 0) {
    Write-Log "Could not commit the phone copy."
    exit $LASTEXITCODE
}
$Gh = "C:\Program Files\GitHub CLI\gh.exe"
$token = & $Gh auth token 2>$null
if (-not $token) {
    Write-Log "Commit succeeded, but GitHub is not signed in, so the phone still has the previous copy."
    exit 1
}
git -c credential.helper= -c "http.extraheader=AUTHORIZATION: bearer $token" push origin HEAD
if ($LASTEXITCODE -ne 0) {
    Write-Log "Commit succeeded, but the push did not. The phone still has the previous copy."
    exit $LASTEXITCODE
}
Write-Log "Pushed a new phone copy."
