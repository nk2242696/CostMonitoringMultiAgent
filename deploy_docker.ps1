# Build and Run Docker Containers for Azure Cost Monitoring with Architecture Review
# This script builds the Docker images and starts all services

Write-Host "=================================" -ForegroundColor Cyan
Write-Host "Azure Cost Monitoring - Docker Deploy" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop existing containers
Write-Host "Step 1: Stopping existing containers..." -ForegroundColor Yellow
docker-compose down
Write-Host "✅ Containers stopped" -ForegroundColor Green
Write-Host ""

# Step 2: Build the Docker images
Write-Host "Step 2: Building Docker images..." -ForegroundColor Yellow
docker-compose build --no-cache
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Images built successfully" -ForegroundColor Green
Write-Host ""

# Step 3: Start the containers
Write-Host "Step 3: Starting containers..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to start containers!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Containers started" -ForegroundColor Green
Write-Host ""

# Step 4: Wait for services to be ready
Write-Host "Step 4: Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check if services are running
Write-Host "Checking service health..." -ForegroundColor Yellow
docker-compose ps

Write-Host ""
Write-Host "=================================" -ForegroundColor Cyan
Write-Host "🚀 Deployment Complete!" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 Access Points:" -ForegroundColor Yellow
Write-Host "   • Grafana Dashboard:          http://localhost:3001" -ForegroundColor White
Write-Host "   • API Documentation:          http://localhost:8000/docs" -ForegroundColor White
Write-Host "   • Architecture Review UI:     http://localhost:8000/static/architecture_review.html" -ForegroundColor White
Write-Host "   • Prometheus:                 http://localhost:9090" -ForegroundColor White
Write-Host ""
Write-Host "🔑 Credentials:" -ForegroundColor Yellow
Write-Host "   • Grafana Username: admin" -ForegroundColor White
Write-Host "   • Grafana Password: AzureCost2025!SecurePass" -ForegroundColor White
Write-Host ""
Write-Host "📊 Dashboards Available:" -ForegroundColor Yellow
Write-Host "   • Azure Cost Trends" -ForegroundColor White
Write-Host "   • AI Recommendations" -ForegroundColor White
Write-Host "   • Architecture Reviews (NEW)" -ForegroundColor Green
Write-Host ""
Write-Host "💡 Next Steps:" -ForegroundColor Yellow
Write-Host "   1. Open Grafana: http://localhost:3001" -ForegroundColor White
Write-Host "   2. Login with credentials above" -ForegroundColor White
Write-Host "   3. Navigate to 'Architecture Review Dashboard'" -ForegroundColor White
Write-Host "   4. Click the embedded UI to run architecture reviews" -ForegroundColor White
Write-Host ""
Write-Host "📝 View Logs:" -ForegroundColor Yellow
Write-Host "   docker-compose logs -f api" -ForegroundColor White
Write-Host ""
Write-Host "🛑 Stop Services:" -ForegroundColor Yellow
Write-Host "   docker-compose down" -ForegroundColor White
Write-Host ""
