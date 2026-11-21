#!/usr/bin/env python3
"""
Test AI Integration for Mondeora
"""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_ai_tools():
    """Test AI Tools Manager"""
    print("\n" + "="*60)
    print("🧪 TESTING AI TOOLS")
    print("="*60)
    
    from ai_agents.ai_tools import get_ai_tools
    
    ai_tools = get_ai_tools()
    available = ai_tools.get_available_tools()
    
    print(f"\n✅ Available AI Tools: {', '.join(available)}")
    
    # Test compression
    if 'headroom' in available:
        test_text = "This is a long product description that needs to be compressed for better processing. " * 10
        compressed = ai_tools.compress_context(test_text, target_ratio=0.5)
        print(f"\n📊 Compression Test:")
        print(f"   Original: {len(test_text)} chars")
        print(f"   Compressed: {len(compressed)} chars")
        print(f"   Ratio: {len(compressed)/len(test_text)*100:.1f}%")


def test_agency_agents():
    """Test Agency Agents Manager"""
    print("\n" + "="*60)
    print("🧪 TESTING AGENCY AGENTS")
    print("="*60)
    
    from ai_agents.agency_integration import get_agency_manager
    
    agency = get_agency_manager()
    
    if agency.agents_cache:
        print(f"\n✅ Loaded {len(agency.agents_cache)} agents")
        
        # Search for e-commerce specialists
        ecommerce = agency.search_agents('e-commerce', limit=3)
        print(f"\n🔍 E-Commerce Specialists:")
        for agent in ecommerce:
            print(f"\n   • {agent['name']}")
            print(f"     Division: {agent['division']}")
            print(f"     {agent['description'][:100]}...")
    else:
        print("\n⚠️  No agents loaded")


def test_dropshipping_assistant():
    """Test Dropshipping AI Assistant"""
    print("\n" + "="*60)
    print("🧪 TESTING DROPSHIPPING AI ASSISTANT")
    print("="*60)
    
    from ai_agents.dropshipping_ai_assistant import get_assistant
    
    assistant = get_assistant()
    
    # Get system status
    status = assistant.get_system_status()
    print(f"\n📊 System Status:")
    print(f"   AI Tools: {', '.join(status['ai_tools'])}")
    print(f"   Agency Agents: {status['agency_agents']}")
    print(f"   Specialists: {', '.join(status['specialists'])}")
    print(f"   Status: {status['status']}")
    
    # Test title optimization
    test_title = "High Quality Premium Waterproof Wireless Bluetooth Speaker Portable Outdoor"
    keywords = ['Lautsprecher', 'Bluetooth', 'Wasserdicht']
    optimized = assistant.optimize_listing_title(test_title, keywords)
    print(f"\n✍️  Title Optimization:")
    print(f"   Original ({len(test_title)} chars): {test_title}")
    print(f"   Optimized ({len(optimized)} chars): {optimized}")
    
    # Get available specialists
    specialists = assistant.get_available_specialists()
    print(f"\n👥 Available Dropshipping Specialists: {len(specialists)}")
    for s in specialists[:3]:
        print(f"   • {s['name']}")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🚀 MONDEORA AI INTEGRATION TEST SUITE")
    print("="*60)
    
    try:
        test_ai_tools()
        test_agency_agents()
        test_dropshipping_assistant()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*60 + "\n")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
