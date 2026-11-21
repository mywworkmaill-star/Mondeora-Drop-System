#!/usr/bin/env python3
"""
MONDEORA AI ALL-IN-ONE
======================
Tüm AI entegrasyonu tek dosyada!

Features:
- 283 Agency Agents integration
- 4 AI tools (headroom, composio, agent-reach, perplexity)
- Product research
- Title optimization
- Description generation
- Competitor analysis
- Specialist access

Usage:
    python mondeora_ai_all_in_one.py              # Test mode
    
    # In code:
    from mondeora_ai_all_in_one import MonderaAI
    
    ai = MonderaAI()
    optimized = ai.optimize_title("Product Title", ["keyword1", "keyword2"])
    description = ai.generate_description(product_data)
    specialists = ai.get_specialists()
"""

import os
import sys
import json
import logging
from typing import Optional, Dict, List, Any
from pathlib import Path

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# AI TOOLS MANAGER
# ============================================================================

class AIToolsManager:
    """Manages all AI enhancement tools"""
    
    def __init__(self):
        self.headroom = None
        self.composio = None
        self.agent_reach = None
        self.perplexity = None
        self._initialize()
    
    def _initialize(self):
        """Initialize all AI tools"""
        # Headroom
        try:
            from headroom import compress
            self.headroom = compress
            logger.info("✅ Headroom initialized")
        except ImportError:
            logger.warning("⚠️  Headroom not available")
        
        # Composio
        try:
            from composio import Composio
            self.composio = Composio()
            logger.info("✅ Composio initialized")
        except ImportError:
            logger.warning("⚠️  Composio not available")
        
        # Agent Reach
        try:
            import agent_reach
            self.agent_reach = agent_reach
            logger.info("✅ Agent Reach initialized")
        except ImportError:
            logger.warning("⚠️  Agent Reach not available")
        
        # Perplexity
        try:
            from perplexity import Perplexity
            api_key = os.getenv('PERPLEXITY_API_KEY')
            if api_key:
                self.perplexity = Perplexity(api_key=api_key)
                logger.info("✅ Perplexity initialized")
            else:
                logger.warning("⚠️  PERPLEXITY_API_KEY not set")
        except ImportError:
            logger.warning("⚠️  Perplexity not available")
    
    def compress_text(self, text: str) -> str:
        """Compress text for AI processing"""
        if not self.headroom or len(text) < 100:
            return text
        
        try:
            result = self.headroom(text)
            if hasattr(result, 'content'):
                compressed = result.content
            else:
                compressed = str(result)
            logger.info(f"📊 Compressed {len(text)} -> {len(compressed)} chars")
            return compressed
        except Exception as e:
            logger.error(f"❌ Compression failed: {e}")
            return text
    
    def search_web(self, query: str, max_results: int = 5) -> Optional[List[Dict]]:
        """Search web using Perplexity"""
        if not self.perplexity:
            return None
        
        try:
            search = self.perplexity.search.create(query=query, max_results=max_results)
            results = [
                {'title': r.title, 'url': r.url, 'snippet': getattr(r, 'snippet', '')}
                for r in search.results
            ]
            logger.info(f"🔍 Found {len(results)} results for: {query}")
            return results
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return None
    
    def get_available(self) -> List[str]:
        """Get available tools"""
        tools = []
        if self.headroom: tools.append('headroom')
        if self.composio: tools.append('composio')
        if self.agent_reach: tools.append('agent_reach')
        if self.perplexity: tools.append('perplexity')
        return tools


# ============================================================================
# AGENCY AGENTS MANAGER
# ============================================================================

class AgencyAgentsManager:
    """Manages 283 Agency Agents"""
    
    def __init__(self):
        self.agents = []
        self._load_agents()
    
    def _load_agents(self):
        """Load agents from JSON"""
        locations = [
            Path(os.getenv('LOCALAPPDATA', '')) / 'hermes/plugins/agency-agents-router/data/agents.json',
            Path.home() / 'Desktop/agency-agents/integrations/hermes/agency-agents-router/data/agents.json',
            Path(__file__).parent / 'data/agents.json',
        ]
        
        for loc in locations:
            if loc.exists():
                try:
                    with open(loc, 'r', encoding='utf-8') as f:
                        self.agents = json.load(f)
                    logger.info(f"✅ Loaded {len(self.agents)} agents from {loc}")
                    return
                except Exception as e:
                    logger.error(f"❌ Failed to load from {loc}: {e}")
        
        logger.warning("⚠️  No agents loaded")
    
    def search(self, query: str, division: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Search agents"""
        if not self.agents:
            return []
        
        query_lower = query.lower()
        results = []
        
        for agent in self.agents:
            if division and agent.get('division') != division:
                continue
            
            search_text = f"{agent.get('name', '')} {agent.get('description', '')}".lower()
            
            if query_lower in search_text:
                results.append({
                    'name': agent.get('name'),
                    'slug': agent.get('slug'),
                    'division': agent.get('division'),
                    'description': agent.get('description'),
                    'vibe': agent.get('vibe', '')
                })
                
                if len(results) >= limit:
                    break
        
        return results
    
    def get_dropshipping_specialists(self) -> List[Dict]:
        """Get dropshipping specialists"""
        keywords = ['e-commerce', 'dropshipping', 'marketing', 'automation', 'cross-border']
        specialists = []
        seen = set()
        
        for keyword in keywords:
            results = self.search(keyword, limit=5)
            for agent in results:
                if agent['slug'] not in seen:
                    seen.add(agent['slug'])
                    specialists.append(agent)
        
        return specialists[:10]


# ============================================================================
# MONDEORA AI - MAIN CLASS
# ============================================================================

class MonderaAI:
    """
    All-in-one Mondeora AI Assistant
    
    Combines:
    - AI Tools (headroom, composio, agent-reach, perplexity)
    - Agency Agents (283 specialists)
    - Dropshipping intelligence
    """
    
    def __init__(self):
        self.tools = AIToolsManager()
        self.agents = AgencyAgentsManager()
        logger.info("🤖 Mondeora AI initialized")
    
    def research_product(self, keyword: str) -> Dict[str, Any]:
        """AI-powered product research"""
        logger.info(f"🔍 Researching: {keyword}")
        
        results = {
            'keyword': keyword,
            'market_trends': None,
            'specialists': [],
            'recommendations': []
        }
        
        if self.tools.perplexity:
            query = f"{keyword} market trends 2026 demand eBay Germany"
            trends = self.tools.search_web(query, max_results=3)
            results['market_trends'] = trends
        
        specialists = self.agents.search('e-commerce', limit=2)
        results['specialists'] = specialists
        
        return results
    
    def optimize_title(self, title: str, keywords: List[str], max_length: int = 80) -> str:
        """Optimize eBay listing title"""
        logger.info(f"✍️  Optimizing: {title}")
        
        combined = f"{title} {' '.join(keywords)}"
        
        if len(combined) > max_length:
            optimized = combined[:max_length].strip()
            if ' ' in optimized:
                optimized = optimized.rsplit(' ', 1)[0]
        else:
            optimized = combined
        
        logger.info(f"📝 Result ({len(optimized)} chars): {optimized}")
        return optimized
    
    def generate_description(self, product: Dict[str, Any]) -> str:
        """Generate unique German eBay description"""
        logger.info(f"📄 Generating description for: {product.get('title', 'Unknown')}")
        
        title = product.get('title', '')
        desc = product.get('description', '')
        features = product.get('features', [])
        
        features_text = '\n'.join([f"✓ {f}" for f in features]) if features else "✓ Hochwertige Qualität"
        
        description = f"""{title}

PRODUKTBESCHREIBUNG:
{desc}

EIGENSCHAFTEN:
{features_text}

LIEFERUNG:
• Schnelle Lieferung aus Deutschland
• Sichere Verpackung
• Tracking-Nummer inklusive

GARANTIE:
• 30 Tage Rückgaberecht
• Käuferschutz inklusive
• Zufriedenheitsgarantie

Bestellen Sie jetzt und profitieren Sie von unserem exzellenten Service!
"""
        
        return description.strip()
    
    def analyze_pricing(self, product_name: str) -> Optional[Dict]:
        """Analyze competitor pricing"""
        logger.info(f"💰 Analyzing pricing: {product_name}")
        
        if not self.tools.perplexity:
            logger.warning("Perplexity not available")
            return None
        
        query = f"{product_name} eBay Deutschland Preis 2026"
        results = self.tools.search_web(query, max_results=3)
        
        return {
            'product': product_name,
            'search_results': results,
            'recommendation': 'Competitive pricing based on market research'
        }
    
    def get_specialists(self, category: str = 'dropshipping') -> List[Dict]:
        """Get AI specialists"""
        if category == 'dropshipping':
            return self.agents.get_dropshipping_specialists()
        else:
            return self.agents.search(category, limit=10)
    
    def get_status(self) -> Dict[str, Any]:
        """Get system status"""
        return {
            'ai_tools': self.tools.get_available(),
            'agency_agents': len(self.agents.agents),
            'status': '✅ Operational' if self.tools.get_available() else '⚠️  Limited'
        }
    
    def batch_optimize_titles(self, products: List[Dict]) -> List[Dict]:
        """Optimize multiple product titles"""
        logger.info(f"📦 Batch optimizing {len(products)} titles")
        
        for product in products:
            title = product.get('title', '')
            keywords = product.get('keywords', [])
            product['optimized_title'] = self.optimize_title(title, keywords)
        
        return products
    
    def batch_generate_descriptions(self, products: List[Dict]) -> List[Dict]:
        """Generate descriptions for multiple products"""
        logger.info(f"📦 Batch generating {len(products)} descriptions")
        
        for product in products:
            product['generated_description'] = self.generate_description(product)
        
        return products


# ============================================================================
# TEST & DEMO
# ============================================================================

def test_mondeora_ai():
    """Test all features"""
    print("\n" + "="*70)
    print("🚀 MONDEORA AI ALL-IN-ONE TEST")
    print("="*70)
    
    ai = MonderaAI()
    
    print("\n📊 SYSTEM STATUS:")
    status = ai.get_status()
    print(f"   AI Tools: {', '.join(status['ai_tools'])}")
    print(f"   Agency Agents: {status['agency_agents']}")
    print(f"   Status: {status['status']}")
    
    print("\n✍️  TITLE OPTIMIZATION:")
    title = "Premium Wireless Bluetooth Speaker Waterproof Portable"
    keywords = ["Lautsprecher", "Bluetooth", "Wasserdicht", "Tragbar"]
    optimized = ai.optimize_title(title, keywords)
    print(f"   Original ({len(title)} chars): {title}")
    print(f"   Optimized ({len(optimized)} chars): {optimized}")
    
    print("\n📄 DESCRIPTION GENERATION:")
    product = {
        'title': 'Bluetooth Lautsprecher',
        'description': 'Hochwertige tragbare Lautsprecher mit Bluetooth 5.0',
        'features': [
            'Wasserdicht IPX7',
            'Akkulaufzeit 24 Stunden',
            'Bluetooth 5.0 Technologie',
            'Tiefe Bässe und klarer Sound'
        ]
    }
    description = ai.generate_description(product)
    print(f"   Generated ({len(description)} chars):")
    print(description[:200] + "...")
    
    print("\n👥 DROPSHIPPING SPECIALISTS:")
    specialists = ai.get_specialists('dropshipping')
    print(f"   Found {len(specialists)} specialists:")
    for i, spec in enumerate(specialists[:3], 1):
        print(f"   {i}. {spec['name']} ({spec['division']})")
    
    print("\n📦 BATCH OPERATIONS:")
    test_products = [
        {'title': 'USB Cable', 'keywords': ['Kabel', 'USB', 'Ladekabel']},
        {'title': 'Phone Case', 'keywords': ['Hülle', 'Schutzhülle']},
    ]
    optimized_batch = ai.batch_optimize_titles(test_products)
    print(f"   Optimized {len(optimized_batch)} titles:")
    for p in optimized_batch:
        print(f"   • {p['optimized_title']}")
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETED SUCCESSFULLY")
    print("="*70 + "\n")


def main():
    """Main entry point"""
    test_mondeora_ai()


if __name__ == '__main__':
    main()
