import os

import httpx

KEY = os.getenv("AZURE_OPENAI_KEY", "")
BASE = os.getenv("AZURE_OPENAI_ENDPOINT", "https://nk224-mj87ojxr-eastus2.openai.azure.com").rstrip("/")

if not KEY:
    raise SystemExit("Set AZURE_OPENAI_KEY before running this script.")

# Try to create a gpt-4o deployment
for api_ver in ["2024-10-21", "2024-06-01", "2023-05-15"]:
    print(f"\nTrying to create deployment with api-version={api_ver}...")
    r = httpx.put(
        f"{BASE}/openai/deployments/gpt-4o?api-version={api_ver}",
        headers={"api-key": KEY, "Content-Type": "application/json"},
        json={
            "model": {"format": "OpenAI", "name": "gpt-4o", "version": "2024-08-06"},
            "sku": {"name": "Standard", "capacity": 10},
        },
        timeout=30,
    )
    print(f"  Status: {r.status_code}")
    print(f"  Body: {r.text[:300]}")
    if r.status_code in (200, 201):
        print("  SUCCESS!")
        break
