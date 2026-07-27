import sys
sys.path.insert(0, 'src')

from monitoring.recommendations.multi_agent_system import MultiAgentSystem

print("Testing MultiAgentSystem initialization...")

# Test 1: Fallback-only mode
print("\n1. Testing fallback-only mode (None, None)...")
try:
    system = MultiAgentSystem(azure_openai_key=None, azure_openai_endpoint=None, db_session=None)
    print(f"✓ Success! fallback_only={system.fallback_only}")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2: With invalid credentials
print("\n2. Testing with invalid credentials...")
try:
    system = MultiAgentSystem(
        azure_openai_key="fake-key",
        azure_openai_endpoint="https://fake-endpoint.openai.azure.com/",
        db_session=None
    )
    print(f"✓ Initialized (error will occur on first query)")
except Exception as e:
    print(f"✗ Error during init: {e}")

print("\nDone!")
