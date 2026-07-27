# Azure Cost Optimization API — Auto-restart wrapper
$env:ENVIRONMENT="dev"
$env:AZURE_OPENAI_ENDPOINT= if ($env:AZURE_OPENAI_ENDPOINT) { $env:AZURE_OPENAI_ENDPOINT } else { "https://kuamnuii.openai.azure.com/" }
$env:AZURE_OPENAI_DEPLOYMENT= if ($env:AZURE_OPENAI_DEPLOYMENT) { $env:AZURE_OPENAI_DEPLOYMENT } else { "gpt-4o" }

if (-not $env:AZURE_OPENAI_KEY) {
    throw "Set AZURE_OPENAI_KEY before running this script."
}

$restartDelay = 3
Write-Host "[API] Starting with auto-restart (Ctrl+C to stop)..." -ForegroundColor Cyan

while ($true) {
    Write-Host "[API] $(Get-Date -Format 'HH:mm:ss') - Launching uvicorn on port 8000" -ForegroundColor Green
    & .\venv\Scripts\python.exe -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        Write-Host "[API] Server exited cleanly (code 0). Stopping." -ForegroundColor Yellow
        break
    }
    Write-Host "[API] Server crashed (exit code $code). Restarting in ${restartDelay}s..." -ForegroundColor Red
    Start-Sleep -Seconds $restartDelay
}
