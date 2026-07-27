"""
Test script to validate the Azure Architecture Agent System
Run this to ensure everything is configured correctly
"""

import os
import sys
from pathlib import Path


def test_imports():
    """Test 1: Check if required packages are installed"""
    print("\n" + "="*80)
    print("TEST 1: Package Imports")
    print("="*80)
    
    required_packages = {
        'autogen': 'pyautogen',
        'openai': 'openai',
        'dotenv': 'python-dotenv'
    }
    
    missing_packages = []
    
    for module_name, package_name in required_packages.items():
        try:
            __import__(module_name)
            print(f"✅ {package_name} installed")
        except ImportError:
            print(f"❌ {package_name} NOT installed")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print(f"Install with: pip install {' '.join(missing_packages)}")
        return False
    
    print("\n✅ All packages installed correctly")
    return True


def test_environment():
    """Test 2: Check environment variables"""
    print("\n" + "="*80)
    print("TEST 2: Environment Configuration")
    print("="*80)
    
    # Try to load .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ .env file loaded")
    except Exception as e:
        print(f"⚠️  Could not load .env file: {e}")
    
    # Check for API keys
    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if azure_key and azure_endpoint:
        print("✅ Azure OpenAI configuration found")
        print(f"   Endpoint: {azure_endpoint[:50]}...")
        print(f"   Model: {os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4')}")
        return True
    elif openai_key:
        print("✅ OpenAI configuration found")
        print(f"   Key: {openai_key[:10]}...{openai_key[-4:]}")
        return True
    else:
        print("❌ No API keys found")
        print("\nPlease set one of:")
        print("  - AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT (Azure OpenAI)")
        print("  - OPENAI_API_KEY (OpenAI)")
        return False


def test_file_structure():
    """Test 3: Check if required files exist"""
    print("\n" + "="*80)
    print("TEST 3: File Structure")
    print("="*80)
    
    required_files = [
        'azure_architecture_agents.py',
        'run_architecture_review.py',
        'examples_architecture_agents.py'
    ]
    
    all_exist = True
    for filename in required_files:
        if Path(filename).exists():
            print(f"✅ {filename} exists")
        else:
            print(f"❌ {filename} NOT FOUND")
            all_exist = False
    
    return all_exist


def test_agent_initialization():
    """Test 4: Try to initialize the agent system"""
    print("\n" + "="*80)
    print("TEST 4: Agent System Initialization")
    print("="*80)
    
    try:
        from azure_architecture_agents import AzureArchitectureAgentSystem
        
        # Try to initialize (without running)
        system = AzureArchitectureAgentSystem(work_dir="./test_output")
        
        print("✅ AzureArchitectureAgentSystem initialized")
        print(f"✅ Agents created:")
        print(f"   - {system.architecture_agent.name}")
        print(f"   - {system.reviewer_agent.name}")
        print(f"   - {system.approver_agent.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return False


def test_quick_run():
    """Test 5: Run a minimal example (if environment is configured)"""
    print("\n" + "="*80)
    print("TEST 5: Quick Run Test (Optional)")
    print("="*80)
    
    response = input("Run a quick test with the agent system? This will use API credits. (y/n): ")
    
    if response.lower() != 'y':
        print("⏭️  Skipped")
        return True
    
    try:
        from azure_architecture_agents import AzureArchitectureAgentSystem
        
        # Minimal problem statement
        problem = "Build a simple REST API on Azure with 1000 requests/day and budget under $50/month."
        
        print("\nRunning architecture review...")
        print(f"Problem: {problem}")
        
        system = AzureArchitectureAgentSystem(work_dir="./test_agent_run")
        results = system.run_full_cycle(problem)
        
        print(f"\n✅ Test run completed!")
        print(f"   Decision: {results['decision']['decision_status']}")
        print(f"   Outputs: ./test_agent_run/")
        
        return True
        
    except Exception as e:
        print(f"❌ Test run failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "🧪 "*30)
    print("AZURE ARCHITECTURE AGENT SYSTEM - VALIDATION TESTS")
    print("🧪 "*30)
    
    tests = [
        ("Package Imports", test_imports),
        ("Environment Config", test_environment),
        ("File Structure", test_file_structure),
        ("Agent Initialization", test_agent_initialization),
        ("Quick Run", test_quick_run)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready to use.")
        print("\nNext steps:")
        print("  1. Run: python run_architecture_review.py --template cost_monitoring")
        print("  2. Or: python examples_architecture_agents.py")
        print("  3. Read: AGENT_SYSTEM_README.md for full documentation")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        sys.exit(1)
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
