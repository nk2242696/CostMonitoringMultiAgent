import os

from openai import AzureOpenAI

KEY = os.getenv("AZURE_OPENAI_KEY", "")
ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://nk224-mj87ojxr-eastus2.openai.azure.com/")

if not KEY:
    raise SystemExit("Set AZURE_OPENAI_KEY before running this script.")

names = [
    "gpt-4o", "gpt-4", "gpt-4o-mini", "gpt-35-turbo", "gpt-4-turbo",
    "gpt-4-32k", "gpt-35-turbo-16k", "gpt-4-0125-preview",
    "nk224", "nk224-mj87ojxr", "chat", "default", "model",
    "gpt-4o-2024-05-13", "gpt-4o-2024-08-06", "gpt-4o-mini-2024-07-18",
]

for api_ver in ["2024-02-15-preview", "2025-01-01-preview", "2024-10-21"]:
    print(f"\n--- api_version: {api_ver} ---")
    client = AzureOpenAI(api_key=KEY, api_version=api_ver, azure_endpoint=ENDPOINT)
    for name in names:
        try:
            r = client.chat.completions.create(
                model=name,
                messages=[{"role": "user", "content": "say hello"}],
                max_tokens=5,
            )
            print(f"  FOUND: {name} works! Response: {r.choices[0].message.content}")
            break
        except Exception as e:
            msg = str(e)[:80]
            if "DeploymentNotFound" in msg or "404" in msg:
                continue
            else:
                print(f"  {name}: {msg}")
    else:
        print("  No deployment found with this API version")
        continue
    break
