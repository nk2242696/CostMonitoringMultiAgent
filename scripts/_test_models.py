import os

from openai import AzureOpenAI

api_key = os.getenv("AZURE_OPENAI_KEY")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "https://kuamnuii.openai.azure.com/")

if not api_key:
    raise SystemExit("Set AZURE_OPENAI_KEY before running this script.")

c = AzureOpenAI(api_key=api_key, api_version="2025-01-01-preview", azure_endpoint=endpoint)
for name in ["gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-35-turbo", "gpt-4-turbo"]:
    try:
        r = c.chat.completions.create(model=name, messages=[{"role": "user", "content": "hi"}], max_tokens=10)
        print(f"  {name}: OK -> {r.choices[0].message.content}")
    except Exception as e:
        msg = str(e)[:80]
        if "DeploymentNotFound" in msg:
            print(f"  {name}: not deployed")
        else:
            print(f"  {name}: {msg}")
