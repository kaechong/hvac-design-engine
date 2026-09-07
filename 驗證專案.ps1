$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$runtimePython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (-not (Test-Path -LiteralPath $runtimePython)) {
    throw '找不到 Codex 附帶 Python。請使用已安裝 Python 3.10+ 執行 scripts/run_checks.py。'
}
Push-Location -LiteralPath $taskRoot
try {
    & $runtimePython 'scripts/run_checks.py'
    if ($LASTEXITCODE -ne 0) { throw '專案驗證未通過，請查看上方具體項目。' }
} finally {
    Pop-Location
}
