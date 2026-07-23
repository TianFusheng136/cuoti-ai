$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "请先运行 start.bat 创建开发环境。"
}

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) { throw "构建 Release 需要 Node.js/npm。" }
Push-Location (Join-Path $root "frontend")
try {
    & $npm.Source ci --include=dev --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "前端依赖安装失败。" }
    & $npm.Source run build
    if ($LASTEXITCODE -ne 0) { throw "前端构建失败。" }
}
finally {
    Pop-Location
}

$lockFile = Join-Path $root "requirements-lock.txt"
if (-not (Test-Path $lockFile)) { throw "缺少 Python 锁文件 requirements-lock.txt。" }
& $python -m pip install --require-hashes -r $lockFile
if ($LASTEXITCODE -ne 0) { throw "Python 锁定依赖安装失败。" }
& $python -m pip install --no-deps -e $root
if ($LASTEXITCODE -ne 0) { throw "Python 项目安装失败。" }
& $python -m ruff check backend
if ($LASTEXITCODE -ne 0) { throw "后端 Ruff 检查失败。" }
& $python -m ruff format --check backend
if ($LASTEXITCODE -ne 0) { throw "后端格式检查失败。" }
& $python -m pytest
if ($LASTEXITCODE -ne 0) { throw "后端测试失败。" }
Push-Location (Join-Path $root "frontend")
try {
    & $npm.Source test
    if ($LASTEXITCODE -ne 0) { throw "前端测试失败。" }
    & $npm.Source run lint
    if ($LASTEXITCODE -ne 0) { throw "前端 TypeScript 检查失败。" }
}
finally {
    Pop-Location
}

$output = Join-Path $root "packaging\output"
$work = Join-Path $root "packaging\build"
Remove-Item $output, $work -Recurse -Force -ErrorAction SilentlyContinue
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $output `
    --workpath $work `
    (Join-Path $root "packaging\windows.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败。" }

$release = Join-Path $output "AIErrorReviewWorkbench"
Copy-Item (Join-Path $root "packaging\start-release.bat") (Join-Path $release "start.bat")
Copy-Item (Join-Path $root "stop.bat") (Join-Path $release "stop.bat")
New-Item -ItemType Directory -Force -Path (Join-Path $release "scripts") | Out-Null
Copy-Item (Join-Path $root "scripts\stop.ps1") (Join-Path $release "scripts\stop.ps1")
Copy-Item (Join-Path $root "packaging\README-RELEASE.txt") (Join-Path $release "使用说明.txt")
Copy-Item (Join-Path $root "LICENSE") (Join-Path $release "LICENSE")
Copy-Item (Join-Path $root "PRIVACY.md") (Join-Path $release "PRIVACY.md")
Copy-Item (Join-Path $root "SECURITY.md") (Join-Path $release "SECURITY.md")
Copy-Item (Join-Path $root "THIRD_PARTY_NOTICES.md") (Join-Path $release "THIRD_PARTY_NOTICES.md")
Copy-Item (Join-Path $root "sbom") (Join-Path $release "sbom") -Recurse

& (Join-Path $root "scripts\smoke-release.ps1") -Release $release
if ($LASTEXITCODE -ne 0) { throw "Release 冒烟测试失败。" }
$releaseData = Join-Path $release "data"
for ($attempt = 0; $attempt -lt 20 -and (Test-Path $releaseData); $attempt++) {
    Start-Sleep -Milliseconds 250
    Remove-Item $releaseData -Recurse -Force -ErrorAction SilentlyContinue
}
if (Test-Path $releaseData) {
    throw "Release 冒烟测试数据未能清理，已停止打包以避免夹带测试数据。"
}

$zip = Join-Path $output "AIErrorReviewWorkbench-windows-x64.zip"
Compress-Archive -Path $release -DestinationPath $zip -CompressionLevel Optimal
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum = Join-Path $output "SHA256SUMS.txt"
[System.IO.File]::WriteAllText(
    $checksum,
    "$hash  AIErrorReviewWorkbench-windows-x64.zip`n",
    [System.Text.UTF8Encoding]::new($false)
)
Write-Host "Release 构建完成：$zip" -ForegroundColor Green
Write-Host "SHA-256：$hash" -ForegroundColor Cyan
