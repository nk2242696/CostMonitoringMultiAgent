# Azure OpenAI Connection Fix

## Problem
The chat system cannot connect to Azure OpenAI from the Docker container due to network restrictions on your Azure OpenAI resource.

Error: `Failed to process query: Connection error`

## Root Cause
Your Azure OpenAI resource (openai-opvc0011.openai.azure.com) has firewall rules that block access from:
- Docker containers
- Unknown IP addresses
- Non-whitelisted networks

## Solutions (Choose One)

### ✅ Option 1: Add Docker Host IP to Azure OpenAI Firewall (Recommended)

1. **Get your public IP:**
   ```powershell
   Invoke-RestMethod -Uri "https://api.ipify.org?format=text"
   ```

2. **Add IP to Azure OpenAI firewall:**
   ```powershell
   # Login to Azure
   az login
   
   # Get your public IP
   $myIP = (Invoke-RestMethod -Uri "https://api.ipify.org?format=text")
   
   # Add IP to Azure OpenAI firewall
   az cognitiveservices account network-rule add `
     --resource-group <your-resource-group> `
     --name openai-opvc0011 `
     --ip-address $myIP
   ```

3. **Refresh the chat** - It should work now!

---

### ✅ Option 2: Enable "Allow Azure Services" (Quick Fix)

1. **Go to Azure Portal:**
   - Navigate to your Azure OpenAI resource: `openai-opvc0011`
   - Go to **Networking** → **Firewalls and virtual networks**

2. **Enable Azure services:**
   - Check ☑️ "Allow Azure services on the trusted services list to access this account"
   - Click **Save**

3. **Wait 1-2 minutes** for changes to propagate

4. **Refresh the chat** - Should work now!

---

### ✅ Option 3: Run API Outside Docker (Testing Only)

Run the API directly on your host machine (bypasses Docker networking):

```powershell
# Stop Docker API
docker stop azure-cost-api

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Set environment variables
$env:AZURE_OPENAI_KEY = "<your-azure-openai-key>"
$env:AZURE_OPENAI_ENDPOINT = "https://openai-opvc0011.openai.azure.com/"
$env:AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
$env:DATABASE_URL = "postgresql://postgres:<your-postgres-password>@localhost:5432/azure_cost_dev"

# Run API
uvicorn src.monitoring.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Then update nginx.conf to point chat API to `host.docker.internal:8000`.

---

## Verify Connection

After applying any fix, test the connection:

```powershell
# From host machine
Invoke-WebRequest -Uri "https://openai-opvc0011.openai.azure.com/" -Headers @{"api-key"="<your-azure-openai-key>"}

# From Docker container
docker exec azure-cost-api python -c "import urllib.request; urllib.request.urlopen('https://openai-opvc0011.openai.azure.com/', timeout=5); print('Connected!')"
```

## Current Status

✅ **Chat UI**: Working perfectly (floating button in Grafana)
✅ **Multi-Agent System**: Code ready (5 agents implemented)
✅ **API Endpoints**: All operational
❌ **Azure OpenAI Connection**: Blocked by firewall

**Once you fix the network access, the entire chat system will work immediately!**

## Quick Test

1. Apply one of the fixes above
2. Open: http://localhost:3001/d/azure-cost-trends
3. Click the 💬 button in bottom-right corner
4. Try a query: "What are my top 3 cost drivers?"
5. The AI agents will analyze your data and provide insights!
