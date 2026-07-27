"""
Setup and verify Azure OpenAI configuration for Architecture Agents
"""
import os


def check_configuration():
    """Check current Azure OpenAI configuration"""
    print("="*80)
    print("🔍 Checking Azure OpenAI Configuration")
    print("="*80 + "\n")
    
    # Check for environment variables
    azure_key = os.getenv("AZURE_OPENAI_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    
    openai_key = os.getenv("OPENAI_API_KEY")
    
    print("Current Configuration:")
    print("-" * 80)
    
    if azure_endpoint:
        print(f"✅ AZURE_OPENAI_ENDPOINT: {azure_endpoint}")
    else:
        print("❌ AZURE_OPENAI_ENDPOINT: Not set")
    
    if azure_key:
        print(f"✅ AZURE_OPENAI_KEY: {azure_key[:20]}...")
    else:
        print("❌ AZURE_OPENAI_KEY: Not set")
    
    if azure_deployment:
        print(f"✅ AZURE_OPENAI_DEPLOYMENT: {azure_deployment}")
    else:
        print("❌ AZURE_OPENAI_DEPLOYMENT: Not set")
    
    if openai_key:
        print(f"✅ OPENAI_API_KEY: {openai_key[:20]}... (alternative)")
    
    print("\n" + "="*80)
    print("💡 Configuration Options")
    print("="*80 + "\n")
    
    print("OPTION 1: Use Azure OpenAI (Recommended)")
    print("-" * 80)
    print("Set these environment variables:\n")
    print('$env:AZURE_OPENAI_KEY = "your-azure-openai-key"')
    print('$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"')
    print('$env:AZURE_OPENAI_DEPLOYMENT = "gpt-4o"  # or your model deployment name')
    print("\nTo get these values:")
    print("1. Go to https://portal.azure.com")
    print("2. Navigate to your Azure OpenAI resource")
    print("3. Go to 'Keys and Endpoint'")
    print("4. Copy Key 1 and Endpoint")
    print("5. Go to 'Model deployments' to see deployment name")
    
    print("\n\nOPTION 2: Use OpenAI API (Alternative)")
    print("-" * 80)
    print("Set this environment variable:\n")
    print('$env:OPENAI_API_KEY = "sk-your-openai-api-key"')
    print("\nTo get an OpenAI API key:")
    print("1. Go to https://platform.openai.com")
    print("2. Sign in or create account")
    print("3. Go to API keys")
    print("4. Create new key")
    
    print("\n\n" + "="*80)
    print("🧪 Testing Connection")
    print("="*80 + "\n")
    
    if azure_endpoint and azure_key:
        print("Testing Azure OpenAI connection...")
        try:
            from openai import AzureOpenAI
            
            client = AzureOpenAI(
                api_key=azure_key,
                api_version="2024-02-15-preview",
                azure_endpoint=azure_endpoint
            )
            
            response = client.chat.completions.create(
                model=azure_deployment or "gpt-4o",
                messages=[{"role": "user", "content": "Say 'Connection successful'"}],
                max_tokens=10
            )
            
            print(f"✅ Azure OpenAI connected successfully!")
            print(f"   Response: {response.choices[0].message.content}")
            return True
            
        except Exception as e:
            print(f"❌ Azure OpenAI connection failed:")
            print(f"   Error: {str(e)}")
            print(f"\n   Common issues:")
            print(f"   - Endpoint URL is wrong (check Azure portal)")
            print(f"   - API key is expired or invalid")
            print(f"   - Deployment name doesn't match")
            print(f"   - Resource is behind firewall/VPN")
            return False
    
    elif openai_key:
        print("Testing OpenAI connection...")
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=openai_key)
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Say 'Connection successful'"}],
                max_tokens=10
            )
            
            print(f"✅ OpenAI connected successfully!")
            print(f"   Response: {response.choices[0].message.content}")
            return True
            
        except Exception as e:
            print(f"❌ OpenAI connection failed:")
            print(f"   Error: {str(e)}")
            return False
    
    else:
        print("❌ No API keys configured")
        print("   Please set environment variables as shown above")
        return False


def main():
    """Run configuration check"""
    success = check_configuration()
    
    print("\n\n" + "="*80)
    print("📝 Next Steps")
    print("="*80 + "\n")
    
    if success:
        print("✅ Configuration is working! You can now run:")
        print("   python run_architecture_agents_simple.py")
    else:
        print("⚠️  Please fix the configuration issues above, then run:")
        print("   python check_architecture_agents_config.py")
        print("\nAfter configuration is fixed, run:")
        print("   python run_architecture_agents_simple.py")
    
    print("\n")


if __name__ == "__main__":
    main()
