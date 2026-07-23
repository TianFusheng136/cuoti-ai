$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$dataDir = Join-Path $root "data"
$runtimeDir = Join-Path $dataDir "runtime"
$logDir = Join-Path $dataDir "logs"
$stateFile = Join-Path $runtimeDir "app.json"
New-Item -ItemType Directory -Force -Path $runtimeDir, $logDir | Out-Null

function Test-PortAvailable([int]$Port) {
    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback, $Port
    )
    try {
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        $listener.Stop()
    }
}

if (Test-Path $stateFile) {
    try {
        $state = Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $existing = Get-Process -Id $state.pid -ErrorAction Stop
        $health = Invoke-RestMethod "$($state.url)/api/v1/health" -TimeoutSec 2
        if ($health.status -eq "ok") {
            Write-Host "AI 错题复盘工作台已经运行：$($state.url)" -ForegroundColor Green
            if ($env:AI_REVIEW_NO_BROWSER -ne "1") { Start-Process $state.url }
            exit 0
        }
    }
    catch {
        Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
    }
}

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "首次启动：正在创建 Python 本地环境……" -ForegroundColor Cyan
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "未找到 Python。开发版需要 Python 3.12；正式 Release 将内置运行环境。"
    }
    & $pythonCommand.Source -m venv (Join-Path $root ".venv")
}

$dependencyStamp = Join-Path $root ".venv\project-dependencies.sha256"
$lockFile = Join-Path $root "requirements-lock.txt"
if (-not (Test-Path $lockFile)) { throw "缺少 Python 锁文件 requirements-lock.txt。" }
$projectHash = (Get-FileHash (Join-Path $root "pyproject.toml") -Algorithm SHA256).Hash
$lockHash = (Get-FileHash $lockFile -Algorithm SHA256).Hash
$dependencyHash = "$projectHash`:$lockHash"
$installedHash = if (Test-Path $dependencyStamp) { (Get-Content $dependencyStamp -Raw).Trim() } else { "" }
if ($installedHash -ne $dependencyHash) {
    Write-Host "正在同步 Python 依赖……" -ForegroundColor Cyan
    & $python -m pip install --require-hashes -r $lockFile
    if ($LASTEXITCODE -ne 0) { throw "Python 锁定依赖安装失败。" }
    & $python -m pip install --no-deps -e $root
    if ($LASTEXITCODE -ne 0) { throw "Python 项目安装失败。" }
    [System.IO.File]::WriteAllText($dependencyStamp, $dependencyHash)
}

$frontendRoot = Join-Path $root "frontend"
$frontendIndex = Join-Path $frontendRoot "dist\index.html"
$frontendNeedsBuild = -not (Test-Path $frontendIndex)
if (-not $frontendNeedsBuild) {
    $buildTime = (Get-Item $frontendIndex).LastWriteTimeUtc
    $newerSource = Get-ChildItem (Join-Path $frontendRoot "src"), (Join-Path $frontendRoot "package.json"), (Join-Path $frontendRoot "index.html") -Recurse -File |
        Where-Object { $_.LastWriteTimeUtc -gt $buildTime } |
        Select-Object -First 1
    $frontendNeedsBuild = $null -ne $newerSource
}
if ($frontendNeedsBuild) {
    Write-Host "正在构建前端页面……" -ForegroundColor Cyan
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) {
        throw "未找到 Node.js/npm。开发版需要 Node.js；正式 Release 将包含已构建页面。"
    }
    Push-Location $frontendRoot
    try {
        & $npm.Source ci --include=dev --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "前端依赖安装失败。" }
        & $npm.Source run build
        if ($LASTEXITCODE -ne 0) { throw "前端构建失败。" }
    }
    finally {
        Pop-Location
    }
}

$port = 3002
if (-not (Test-PortAvailable $port)) {
    throw "端口 3002 已被占用，请先关闭占用该端口的程序。"
}

$url = "http://127.0.0.1:3002"
$stdoutLog = Join-Path $logDir "server.log"
$stderrLog = Join-Path $logDir "server-error.log"
$process = Start-Process -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "$port") `
    -WorkingDirectory $root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog

$state = @{
    pid = $process.Id
    url = $url
    port = $port
    processStartTimeUtc = $process.StartTime.ToUniversalTime().ToString("o")
} | ConvertTo-Json
[System.IO.File]::WriteAllText($stateFile, $state, [System.Text.UTF8Encoding]::new($false))

$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 250
    if ($process.HasExited) { break }
    try {
        $health = Invoke-RestMethod "$url/api/v1/health" -TimeoutSec 1
        if ($health.status -eq "ok") { $ready = $true; break }
    }
    catch { }
}

if (-not $ready) {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
    Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
    throw "本地服务启动失败，请查看 data\logs\server-error.log。"
}

Write-Host "AI 错题复盘工作台已启动：$url" -ForegroundColor Green
if ($env:AI_REVIEW_NO_BROWSER -ne "1") { Start-Process $url }
