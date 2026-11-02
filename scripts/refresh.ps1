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

function Format-CommandOutput($Output) {
    if ($null -eq $Output) {
        return ""
    }
    return (($Output | ForEach-Object { "$_" }) -join " ").Trim()
}

function Push-PhoneCopy {
    $env:Path = "C:\Program Files\GitHub CLI;" + $env:Path
    $env:GIT_TERMINAL_PROMPT = "0"
    $gitCred = @("-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential")
    $maxAttempts = 5

    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        $pushOut = & git @gitCred push origin HEAD 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Log "Pushed a new phone copy."
            return 0
        }

        $text = Format-CommandOutput $pushOut
        Write-Log ("Push attempt {0}/{1} failed: {2}" -f $attempt, $maxAttempts, $text)

        if ($text -match "non-fast-forward|fetch first|\[rejected\]") {
            $pullOut = & git @gitCred pull --rebase --autostash origin HEAD 2>&1
            Write-Log ("Rebase after rejected push: {0}" -f (Format-CommandOutput $pullOut))
            if ($LASTEXITCODE -ne 0) {
                Write-Log "Could not rebase onto origin. Leaving the local commit for the next run."
                return $LASTEXITCODE
            }
        }

        if ($attempt -lt $maxAttempts) {
            Start-Sleep -Seconds (5 * $attempt)
        }
    }

    Write-Log "Commit succeeded, but the push did not after $maxAttempts attempts. The phone still has the previous copy."
    return 1
}

Set-Location $Backend
& $Python -m app.db.backup
if ($LASTEXITCODE -ne 0) {
    Write-Log "Backup failed. Fetch was not started."
    exit $LASTEXITCODE
}

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

$env:Path = "C:\Program Files\GitHub CLI;" + $env:Path
$env:GIT_TERMINAL_PROMPT = "0"
$gitCred = @("-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential")

git add -- docs
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "Update the phone feed."
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Could not commit the phone copy."
        exit $LASTEXITCODE
    }
}

$fetchOut = & git @gitCred fetch origin 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Log ("Could not fetch origin before push: {0}" -f (Format-CommandOutput $fetchOut))
}

$ahead = 0
$aheadText = & git rev-list --count "origin/main..HEAD" 2>&1
if ($LASTEXITCODE -eq 0) {
    $ahead = [int]$aheadText
}

if ($ahead -le 0) {
    Write-Log "Phone copy unchanged."
    exit 0
}

$pushCode = Push-PhoneCopy
exit $pushCode
