"""
Simple script to collect costs from multiple subscriptions
Run this after starting Docker Desktop
"""
import subprocess
import sys

print("=" * 80)
print("Multi-Subscription Cost Collection")
print("=" * 80)
print()
print("This script will collect cost data from all accessible Azure subscriptions.")
print()
print("Prerequisites:")
print("1. Docker Desktop must be running")
print("2. Azure CLI must be authenticated (az login)")
print()

response = input("Do you want to continue? (y/n): ")
if response.lower() != 'y':
    print("Cancelled.")
    sys.exit(0)

print()
print("Starting collection...")
print()

# Run the collection script
result = subprocess.run(
    [sys.executable, 'collect_all_subscriptions.py'],
    shell=True
)

sys.exit(result.returncode)
