# Start API Server Script
$env:AZURE_OPENAI_ENDPOINT = if ($env:AZURE_OPENAI_ENDPOINT) { $env:AZURE_OPENAI_ENDPOINT } else { "https://openai-opvc0011.openai.azure.com/" }
$env:AZURE_OPENAI_DEPLOYMENT = if ($env:AZURE_OPENAI_DEPLOYMENT) { $env:AZURE_OPENAI_DEPLOYMENT } else { "gpt-4o" }
$env:ENVIRONMENT = "dev"

if (-not $env:AZURE_OPENAI_KEY) {
	throw "Set AZURE_OPENAI_KEY before running this script."
}

Write-Host "Starting Azure Cost Monitoring API..." -ForegroundColor Green
Write-Host "API will be available at: http://localhost:8000" -ForegroundColor Cyan
Write-Host ""

python -m uvicorn src.monitoring.api.main:app --host 0.0.0.0 --port 8000
