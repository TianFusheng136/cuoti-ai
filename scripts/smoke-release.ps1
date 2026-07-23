param(
    [string]$Release = (Join-Path (Split-Path -Parent $PSScriptRoot) "packaging\output\AIErrorReviewWorkbench")
)
$ErrorActionPreference = "Stop"
$env:AI_REVIEW_NO_BROWSER = "1"
$process = Start-Process `
    -FilePath (Join-Path $Release "AIErrorReviewWorkbench.exe") `
    -WorkingDirectory $Release `
    -PassThru
$stateFile = Join-Path $Release "data\runtime\app.json"
$ready = $false
try {
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 250
        if (-not (Test-Path $stateFile)) { continue }
        try {
            $state = Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
            $health = Invoke-RestMethod "$($state.url)/api/v1/health" -TimeoutSec 1
            if ($health.status -eq "ok") { $ready = $true; break }
        }
        catch { }
    }
    if (-not $ready) { throw "打包后的应用未能通过健康检查。" }
    $index = Invoke-WebRequest $state.url -UseBasicParsing
    if ($index.Content -notmatch "AI 错题复盘") { throw "打包后的应用缺少前端页面。" }
    if ($index.Headers["X-Frame-Options"] -ne "DENY") { throw "Release 缺少安全响应头。" }
    $docsStatus = 0
    try {
        $docsStatus = (Invoke-WebRequest "$($state.url)/api/docs" -UseBasicParsing).StatusCode
    }
    catch {
        if ($null -ne $_.Exception.Response) {
            $docsStatus = [int]$_.Exception.Response.StatusCode
        }
    }
    if ($docsStatus -ne 404) { throw "Release 不应开放 API 文档。" }
    $notebook = Invoke-RestMethod "$($state.url)/api/v1/notebook"
    if ($null -eq $notebook.facets.total) { throw "打包后的错题本 API 响应无效。" }
    Write-Host "Release 冒烟测试通过：$($state.url)" -ForegroundColor Green
}
finally {
    if (-not $process.HasExited) { Stop-Process $process.Id -Force }
    Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
}
