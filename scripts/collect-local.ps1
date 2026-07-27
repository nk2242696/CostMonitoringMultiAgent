[CmdletBinding()]
param(
    [ValidateRange(1, 365)]
    [int]$Days = 30,

    [switch]$SkipRecommendations
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot

try {
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        throw "Azure CLI is required. Install it and run 'az login' first."
    }

    $account = az account show --output json | ConvertFrom-Json
    if (-not $account.id) {
        throw "Azure CLI is not signed in. Run 'az login' first."
    }

    $token = az account get-access-token `
        --resource https://management.azure.com/ `
        --output json | ConvertFrom-Json

    if (-not $token.accessToken -or -not $token.expires_on) {
        throw "Azure CLI did not return a usable management token."
    }

    # Keep the delegated token in process memory only. It is never written to .env.
    $env:AZURE_ACCESS_TOKEN = $token.accessToken
    $env:AZURE_ACCESS_TOKEN_EXPIRES_ON = [string]$token.expires_on

    Write-Host "Collecting $Days days of Azure costs using the signed-in Azure CLI account..."
    docker compose run --rm `
        -e AZURE_ACCESS_TOKEN `
        -e AZURE_ACCESS_TOKEN_EXPIRES_ON `
        api cost-monitor collect --days $Days
    if ($LASTEXITCODE -ne 0) {
        throw "Azure cost collection failed."
    }

    if (-not $SkipRecommendations) {
        Write-Host "Generating recommendations..."
        docker compose run --rm api cost-monitor recommend
        if ($LASTEXITCODE -ne 0) {
            throw "Recommendation generation failed."
        }
    }

    Write-Host "Collection completed. Refresh Grafana at http://localhost:3000."
}
finally {
    Remove-Item Env:AZURE_ACCESS_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:AZURE_ACCESS_TOKEN_EXPIRES_ON -ErrorAction SilentlyContinue
    Pop-Location
}
