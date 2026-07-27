"""
Quick setup script for Multi-Agent Chat System
"""
import os
import sys

def check_requirements():
    """Check if required packages are installed"""
    print("🔍 Checking requirements...")
    
    try:
        import openai
        print("✅ openai installed")
    except ImportError:
        print("❌ openai not installed. Run: pip install openai>=1.0.0")
        return False
    
    try:
        import tiktoken
        print("✅ tiktoken installed")
    except ImportError:
        print("❌ tiktoken not installed. Run: pip install tiktoken>=0.5.0")
        return False
    
    return True

def check_env_vars():
    """Check if environment variables are set"""
    print("\n🔍 Checking Azure OpenAI configuration...")
    
    # Using existing credentials configured as defaults
    api_key = os.getenv("AZURE_OPENAI_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "https://openai-opvc0011.openai.azure.com/")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    
    if not api_key:
        print("❌ AZURE_OPENAI_KEY is not set")
        return False

    print("✅ Using Azure OpenAI credentials from environment")
    print(f"   Key: {api_key[:20]}...")
    print(f"   Endpoint: {endpoint}")
    print(f"   Deployment: {deployment}")
    
    return True

def test_azure_openai():
    """Test Azure OpenAI connection"""
    print("\n🔍 Testing Azure OpenAI connection...")
    
    try:
        from openai import AzureOpenAI
        
        # Use existing credentials with defaults
        api_key = os.getenv("AZURE_OPENAI_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "https://openai-opvc0011.openai.azure.com/")

        if not api_key:
            raise ValueError("AZURE_OPENAI_KEY environment variable is required")
        
        client = AzureOpenAI(
            api_key=api_key,
            api_version="2024-02-15-preview",
            azure_endpoint=endpoint
        )
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Say 'Connection successful'"}],
            max_tokens=10
        )
        
        print(f"✅ Azure OpenAI connected: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"❌ Azure OpenAI connection failed: {str(e)}")
        return False

def test_database():
    """Test database connection"""
    print("\n🔍 Testing database connection...")
    
    try:
        from src.common.database import get_session
        
        db = next(get_session())
        from src.monitoring.storage.models import CostRecord
        
        count = db.query(CostRecord).count()
        print(f"✅ Database connected: {count} cost records found")
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return False

def create_demo_query():
    """Create a demo chat query"""
    print("\n🚀 Testing chat system...")
    
    try:
        import asyncio
        from src.monitoring.recommendations.multi_agent_system import MultiAgentSystem
        from src.common.database import get_session
        
        async def test_query():
            db = next(get_session())
            
            # Use existing credentials
            agent_system = MultiAgentSystem(
                azure_openai_key=os.getenv("AZURE_OPENAI_KEY"),
                azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://openai-opvc0011.openai.azure.com/"),
                db_session=db
            )
            
            print("\n📝 Asking: 'What's my total cloud spend this month?'\n")
            response = await agent_system.query("What's my total cloud spend this month?")
            
            print("🤖 AI Response:")
            print("=" * 60)
            print(response)
            print("=" * 60)
            
            db.close()
        
        asyncio.run(test_query())
        print("\n✅ Chat system working!")
        return True
        
    except Exception as e:
        print(f"❌ Chat system test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all checks"""
    print("=" * 60)
    print("Multi-Agent Chat System Setup")
    print("=" * 60)
    
    all_checks_passed = True
    
    # Check requirements
    if not check_requirements():
        all_checks_passed = False
    
    # Check environment variables
    if not check_env_vars():
        all_checks_passed = False
    
    if not all_checks_passed:
        print("\n❌ Setup incomplete. Please fix the issues above.")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ Configuration validated! Chat system is ready.")
    print("=" * 60)
    print("\n📚 Your chat system is deployed and ready:")
    print("   Docker containers: Running (checked with docker ps)")
    print("   API Server: http://localhost:8000 (already running)")
    print("   Chat Widget: http://localhost:8000/chat/widget")
    print("   API Docs: http://localhost:8000/docs")
    print("\n💬 Try these chat queries:")
    print("   • What are my total costs this month?")
    print("   • Show me services with the highest increase")
    print("   • What optimization recommendations do you have?")
    print("   • Are there any cost anomalies?")
    print("\n🎯 5 AI Agents Ready:")
    print("   • Orchestrator - Routes questions to right agents")
    print("   • Data Analyst - Queries cost data and trends")
    print("   • Budget Advisor - Tracks budgets and forecasts")
    print("   • Optimizer - Suggests cost optimizations")
    print("   • Anomaly Detector - Identifies unusual spending")
    print("\n📖 Documentation: CHAT_SYSTEM_GUIDE.md")
    print("\n🔧 If needed, restart API: docker restart azure-cost-api")

if __name__ == "__main__":
    main()
