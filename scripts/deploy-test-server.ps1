[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$ServerHost = "172.30.30.58",

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$ServerUser = "root",

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$RemoteRoot = "/opt/loan-interest-accrual",

    [Parameter()]
    [ValidateRange(1, 65535)]
    [int]$HostPort = 18082,

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$ServiceName = "loan-interest-accrual-test",

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$RemotePython = "/opt/intpp-backend/venv/bin/python",

    [Parameter()]
    [string]$ReleaseTag = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param([Parameter(Mandatory = $true)][string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

function Assert-RequiredFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description is required: $Path"
    }
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $projectRoot

Assert-RequiredFile -Path (Join-Path $projectRoot "requirements.txt") -Description "Pinned requirements"

$trackedStatus = @(& git status --porcelain --untracked-files=no)
Assert-LastExitCode "git tracked status"
if ($trackedStatus.Count -ne 0) {
    throw "Tracked working tree changes must be committed before deployment."
}

$commit = (& git rev-parse HEAD).Trim()
Assert-LastExitCode "git commit resolution"
$shortCommit = (& git rev-parse --short=12 HEAD).Trim()
Assert-LastExitCode "git short commit resolution"

if ([string]::IsNullOrWhiteSpace($ReleaseTag)) {
    $ReleaseTag = "chenyali-$shortCommit-r$((Get-Date).ToString('yyyyMMddHHmmss'))"
}
if ($ReleaseTag -notmatch "^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$") {
    throw "ReleaseTag contains unsupported characters: $ReleaseTag"
}

$artifactRoot = Join-Path $projectRoot ".artifacts\deploy-test-server-v1"
$packageRoot = Join-Path $artifactRoot "package"
$wheelhouseRoot = Join-Path $artifactRoot "wheelhouse-linux"
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null
if (Test-Path -LiteralPath $wheelhouseRoot) {
    Remove-Item -LiteralPath $wheelhouseRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $wheelhouseRoot -Force | Out-Null

& .\.venv\Scripts\python.exe `
    -m pip download `
    --dest $wheelhouseRoot `
    --platform manylinux2014_x86_64 `
    --python-version 312 `
    --implementation cp `
    --abi cp312 `
    --only-binary=:all: `
    --requirement requirements.txt
Assert-LastExitCode "Linux wheelhouse download"

$archiveName = "$ReleaseTag.tar"
$archivePath = Join-Path $packageRoot $archiveName
if (Test-Path -LiteralPath $archivePath -PathType Leaf) {
    Remove-Item -LiteralPath $archivePath -Force
}
$wheelhouseArchiveName = "$ReleaseTag-wheelhouse.tar"
$wheelhouseArchivePath = Join-Path $packageRoot $wheelhouseArchiveName
if (Test-Path -LiteralPath $wheelhouseArchivePath -PathType Leaf) {
    Remove-Item -LiteralPath $wheelhouseArchivePath -Force
}

& git archive --format=tar --output=$archivePath HEAD
Assert-LastExitCode "git archive"
Assert-RequiredFile -Path $archivePath -Description "Release source archive"
& tar -cf $wheelhouseArchivePath -C $wheelhouseRoot .
Assert-LastExitCode "Linux wheelhouse archive"
Assert-RequiredFile -Path $wheelhouseArchivePath -Description "Linux wheelhouse archive"

$remote = "$ServerUser@$ServerHost"
$remoteArchive = "/tmp/$archiveName"
$remoteWheelhouseArchive = "/tmp/$wheelhouseArchiveName"
& ssh -o BatchMode=yes -o ConnectTimeout=10 $remote "mkdir -p /tmp"
Assert-LastExitCode "remote tmp directory check"
& scp -q $archivePath "${remote}:$remoteArchive"
Assert-LastExitCode "release archive upload"
& scp -q $wheelhouseArchivePath "${remote}:$remoteWheelhouseArchive"
Assert-LastExitCode "Linux wheelhouse upload"

$remoteScript = @"
set -euo pipefail

remote_root='$RemoteRoot'
release_tag='$ReleaseTag'
commit='$commit'
service_name='$ServiceName'
remote_python='$RemotePython'
host_port='$HostPort'
remote_archive='$remoteArchive'
remote_wheelhouse_archive='$remoteWheelhouseArchive'
release_dir="`$remote_root/releases/`$release_tag"
source_dir="`$release_dir/source"
wheelhouse_dir="`$release_dir/wheelhouse"
venv_dir="`$release_dir/venv"
service_file="/etc/systemd/system/`$service_name.service"

if [ ! -x "`$remote_python" ]; then
  echo "Required Python 3.12 executable is missing: `$remote_python" >&2
  exit 20
fi
"`$remote_python" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 21)
PY

mkdir -p "`$source_dir" "`$wheelhouse_dir"
tar -xf "`$remote_archive" -C "`$source_dir"
tar -xf "`$remote_wheelhouse_archive" -C "`$wheelhouse_dir"

if systemctl list-unit-files | awk '{print `$1}' | grep -Fx "`$service_name.service" >/dev/null; then
  systemctl stop "`$service_name.service" || true
fi

if ss -ltn "sport = :`$host_port" | grep -q LISTEN; then
  echo "Host port `$host_port is already in use after stopping `$service_name." >&2
  exit 22
fi

"`$remote_python" -m venv "`$venv_dir"
"`$venv_dir/bin/python" -m pip install \
  --no-index \
  --find-links "`$wheelhouse_dir" \
  --requirement "`$source_dir/requirements.txt"
"`$venv_dir/bin/python" -m pip check

cat > "`$service_file" <<SERVICE
[Unit]
Description=Loan Interest Accrual Test Server
After=network.target

[Service]
Type=simple
WorkingDirectory=`$source_dir
Environment=PYTHONPATH=`$source_dir/src
Environment=LIA_RELEASE_TAG=`$release_tag
Environment=LIA_RELEASE_COMMIT=`$commit
ExecStart=`$venv_dir/bin/python -m uvicorn loan_interest_accrual.web:app --app-dir `$source_dir/src --host 0.0.0.0 --port `$host_port
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable "`$service_name.service" >/dev/null
systemctl restart "`$service_name.service"

for attempt in `$(seq 1 40); do
  if curl -fsS "http://127.0.0.1:`$host_port/health" >/tmp/loan-interest-accrual-health.json; then
    break
  fi
  sleep 1
done

curl -fsS "http://127.0.0.1:`$host_port/health"
printf '\n'
cat > "`$remote_root/current-release.json" <<JSON
{
  "releaseTag": "`$release_tag",
  "commit": "`$commit",
  "serviceName": "`$service_name",
  "releaseDir": "`$release_dir",
  "hostPort": `$host_port,
  "healthUrl": "http://127.0.0.1:`$host_port/health"
}
JSON

systemctl --no-pager --full status "`$service_name.service" | head -n 12
"@

$remoteScriptName = "$ReleaseTag-remote-deploy.sh"
$remoteScriptPath = Join-Path $packageRoot $remoteScriptName
$remoteDeployScript = "/tmp/$remoteScriptName"
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText(
    $remoteScriptPath,
    $remoteScript.Replace("`r`n", "`n"),
    $utf8NoBom
)
& scp -q $remoteScriptPath "${remote}:$remoteDeployScript"
Assert-LastExitCode "remote deployment script upload"
& ssh -o BatchMode=yes -o ConnectTimeout=10 $remote "bash '$remoteDeployScript'"
Assert-LastExitCode "remote test deployment"

[pscustomobject]@{
    status = "pass"
    release_tag = $ReleaseTag
    commit = $commit
    server = $ServerHost
    remote_root = $RemoteRoot
    service = $ServiceName
    url = "http://${ServerHost}:$HostPort/"
    health_url = "http://${ServerHost}:$HostPort/health"
} | ConvertTo-Json -Depth 3
