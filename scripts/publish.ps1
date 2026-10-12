param([switch]$SkipTests)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$repository = 'Alfa-jim/darkcoal-qwen-image-21'

function Assert-NativeSuccess([string]$operation) {
    if ($LASTEXITCODE -ne 0) { throw "$operation failed (exit $LASTEXITCODE)" }
}

gh auth status --hostname github.com
Assert-NativeSuccess 'GitHub authentication; run gh auth login --hostname github.com --web'
$login = gh api user --jq '.login'
Assert-NativeSuccess 'Reading authenticated login'
if ($login -ne 'Alfa-jim') { throw "Expected Alfa-jim; authenticated as $login" }

if (-not $SkipTests) {
    python -m unittest discover -s tests -v
    Assert-NativeSuccess 'Worker tests'
    python scripts/make_download_command.py --check
    Assert-NativeSuccess 'Pasteable command verification'
}

$commit = git rev-parse HEAD
Assert-NativeSuccess 'Reading committed project; initialize and commit first'
$dirty = git status --porcelain
if ($dirty) { throw 'Commit your source changes before publishing; no files are committed automatically.' }
$branch = git branch --show-current
if ($branch -ne 'main') { throw "Expected new standalone project branch main; found $branch" }

$remote = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    gh repo create $repository --public --source . --remote origin --description 'Qwen Image 2.1 Turbo Q4 RunPod worker with network-volume models and up to 10 references'
    Assert-NativeSuccess 'Creating public repository'
} elseif ($remote -notin @('https://github.com/Alfa-jim/darkcoal-qwen-image-21.git', 'git@github.com:Alfa-jim/darkcoal-qwen-image-21.git')) {
    throw "Unexpected origin: $remote"
}

git push -u origin main
Assert-NativeSuccess 'Pushing main'
Start-Sleep -Seconds 5
$runId = gh run list --repo $repository --workflow build.yml --commit $commit --limit 1 --json databaseId --jq '.[0].databaseId'
Assert-NativeSuccess 'Finding build workflow'
if (-not $runId) { throw 'Build not visible yet. Check gh run list --repo Alfa-jim/darkcoal-qwen-image-21, then watch its run id.' }
gh run watch $runId --repo $repository --exit-status
Assert-NativeSuccess 'Container build/publish workflow'
python scripts/verify_registry.py --tag "sha-$commit"
Assert-NativeSuccess 'Anonymous GHCR verification'
Write-Host 'Published and anonymously verified. Use the digest in publication.json for RunPod.'
