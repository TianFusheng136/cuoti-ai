$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "请先创建 .venv 并安装项目依赖。" }
if (-not (Get-Command uv.exe -ErrorAction SilentlyContinue)) { throw "生成 SBOM 需要 uv。" }
if (-not (Get-Command npx.cmd -ErrorAction SilentlyContinue)) { throw "生成 SBOM 需要 Node.js/npx。" }

$sbom = Join-Path $root "sbom"
$runtimeLock = Join-Path $root "data\requirements-runtime-lock.txt"
New-Item -ItemType Directory -Force -Path $sbom, (Split-Path $runtimeLock) | Out-Null

& uv.exe lock
if ($LASTEXITCODE -ne 0) { throw "Python 锁文件生成失败。" }
& uv.exe export --all-extras --format requirements-txt --no-emit-project --output-file "requirements-lock.txt"
if ($LASTEXITCODE -ne 0) { throw "Python 构建依赖导出失败。" }
& uv.exe export --format requirements-txt --no-emit-project --no-hashes --output-file $runtimeLock
if ($LASTEXITCODE -ne 0) { throw "Python 运行依赖导出失败。" }

$env:PYTHONIOENCODING = "utf-8"
& uvx.exe --from cyclonedx-bom cyclonedx-py requirements $runtimeLock `
    --pyproject (Join-Path $root "pyproject.toml") --output-reproducible `
    --of JSON -o (Join-Path $sbom "python.cdx.json") --validate
if ($LASTEXITCODE -ne 0) { throw "Python SBOM 生成失败。" }
& $python (Join-Path $root "scripts\link-python-sbom.py")
if ($LASTEXITCODE -ne 0) { throw "Python SBOM 根依赖关联失败。" }

Push-Location (Join-Path $root "frontend")
try {
    & npx.cmd --yes "@cyclonedx/cyclonedx-npm" --omit dev --gather-license-texts `
        --output-reproducible --of JSON -o (Join-Path $sbom "frontend.cdx.json") `
        --validate package.json
    if ($LASTEXITCODE -ne 0) { throw "前端 SBOM 生成失败。" }
}
finally {
    Pop-Location
}

& uvx.exe pip-licenses --python $python --from=mixed --format=markdown --with-urls `
    --with-license-file --with-notice-file --no-license-path `
    --ignore-packages ai-error-review-workbench `
    --output-file (Join-Path $sbom "python-licenses.md")
if ($LASTEXITCODE -ne 0) { throw "Python 许可清单生成失败。" }

Write-Host "SBOM 与第三方许可清单已更新。" -ForegroundColor Green
