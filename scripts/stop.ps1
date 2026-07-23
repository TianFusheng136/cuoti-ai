$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$stateFile = Join-Path $root "data\runtime\app.json"

if (-not (Test-Path $stateFile)) {
    Write-Host "AI 错题复盘工作台当前没有运行。"
    exit 0
}

try {
    $state = Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $process = Get-Process -Id $state.pid -ErrorAction Stop
    $recordedStart = [DateTime]::Parse($state.processStartTimeUtc).ToUniversalTime()
    $actualStart = $process.StartTime.ToUniversalTime()

    if ([Math]::Abs(($actualStart - $recordedStart).TotalSeconds) -gt 2) {
        throw "PID 已被其他程序使用，为安全起见没有停止该进程。"
    }

    Stop-Process -Id $process.Id -Force
    $process.WaitForExit()
    Write-Host "AI 错题复盘工作台已停止。" -ForegroundColor Green
}
catch [Microsoft.PowerShell.Commands.ProcessCommandException] {
    Write-Host "服务进程已经退出。"
}
finally {
    Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
}
