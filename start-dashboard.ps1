param(
    [switch]$Demo,
    [ValidateRange(1024, 65535)]
    [int]$Port = 8765
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$arguments = @('dashboard.py', '--port', [string]$Port)
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = Join-Path $projectRoot '.factory/tools-venv/Scripts/python.exe'
}
if (-not (Test-Path -LiteralPath $python)) {
    $python = 'python'
}
if ($Demo) {
    $arguments += '--demo'
}
Push-Location $projectRoot
try {
    & $python @arguments
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
exit $exitCode
