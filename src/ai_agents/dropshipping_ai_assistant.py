"""
Dropshipping AI Assistant
Combines Agency Agents + AI Tools for intelligent dropshipping automation

Features:
- Product research with AI
- Listing optimization
- Market analysis
- Competitor research
- Content generation
"""

import logging
from typing import Optional, Dict, List, Any
from .ai_tools import get_ai_tools
from .agency_integration import get_agency_manager, MONDEORA_SPECIALISTS

logger = logging.getLogger(__name__)


class DropshippingAIAssistant:
    """
    AI-powered assistant for dropshipping operations
    """
    
    def __init__(self):
        self.ai_tools = get_ai_tools()
        self.agency = get_agency_manager()
        logger.info("🤖 Dropshipping AI Assistant initialized")
    
    def research_product(self, product_keyword: str) -> Dict[str, Any]:
        """
        AI-powered product research
        
        Args:
            product_keyword: Product keyword to research
        
        Returns:
            Research results with market data, trends, competition
        """
        logger.info(f"🔍 Researching product: {product_keyword}")
        
        results = {
            'keyword': product_keyword,
            'market_trends': None,
            'competition': None,
            'recommendations': []
        }
        
        # Use Perplexity for market research
        if self.ai_tools.perplexity:
            query = f"{product_keyword} market trends 2026 demand analysis"
            trends = self.ai_tools.search_web(query, max_results=3)
            results['market_trends'] = trends
        
        # Get recommendations from e-commerce specialist
        specialist = self.agency.get_agent(MONDEORA_SPECIALISTS['cross_border'])
        if specialist:
            results['recommendations'].append({
                'source': 'Cross-Border E-Commerce Specialist',
                'advice': specialist.get('description', '')
            })
        
        return results
    
    def optimize_listing_title(self, product_title: str, keywords: List[str]) -> str:
        """
        Optimize eBay listing title with AI
        
        Args:
            product_title: Original product title
            keywords: Target keywords
        
        Returns:
            Optimized title (max 80 chars)
        """
        logger.info(f"✍️  Optimizing title for: {product_title}")
        
        # Combine title and keywords
        combined = f"{product_title} {' '.join(keywords)}"
        
        # Use headroom to compress if too long
        if len(combined) > 80:
            compressed = self.ai_tools.compress_context(combined, target_ratio=0.7)
            optimized = compressed[:80].strip()
        else:
            optimized = combined[:80].strip()
        
        logger.info(f"📝 Optimized: {optimized}")
        return optimized
    
    def analyze_competitor_pricing(self, product_name: str) -> Optional[Dict]:
        """
        Analyze competitor pricing with AI search
        
        Args:
            product_name: Product name
        
        Returns:
            Pricing analysis
        """
        logger.info(f"💰 Analyzing pricing for: {product_name}")
        
        if not self.ai_tools.perplexity:
            logger.warning("Perplexity not available")
            return None
        
        query = f"{product_name} eBay Germany price range 2026"
        results = self.ai_tools.search_web(query, max_results=3)
        
        return {
            'product': product_name,
            'analysis': results,
            'recommendation': 'Use competitive pricing based on research'
        }
    
    def generate_product_description(self, product_data: Dict) -> str:
        """
        Generate unique product description
        
        Args:
            product_data: Product information
        
        Returns:
            Generated description
        """
        logger.info(f"📄 Generating description for: {product_data.get('title', 'Unknown')}")
        
        # Use cross-border specialist insights
        specialist = self.agency.get_agent(MONDEORA_SPECIALISTS['cross_border'])
        
        # Create description template
        description = f"""
{product_data.get('title', '')}

PRODUKTBESCHREIBUNG:
{product_data.get('description', '')}

EIGENSCHAFTEN:
{self._format_features(product_data.get('features', []))}

LIEFERUNG:
Schnelle Lieferung aus Deutschland
Sichere Verpackung
Tracking-Nummer inklusive

GARANTIE:
30 Tage Rückgaberecht
Käuferschutz inklusive

Bestellen Sie jetzt!
"""
        
        return description.strip()
    
    def _format_features(self, features: List[str]) -> str:
        """Format product features as bullet points"""
        if not features:
            return "• Hochwertige Qualität"
        return '\n'.join([f"• {feature}" for feature in features])
    
    def get_available_specialists(self) -> List[Dict]:
        """Get available Agency Agents specialists for dropshipping"""
        return self.agency.get_dropshipping_specialists()
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get AI system status"""
        return {
            'ai_tools': self.ai_tools.get_available_tools(),
            'agency_agents': len(self.agency.agents_cache) if self.agency.agents_cache else 0,
            'specialists': list(MONDEORA_SPECIALISTS.keys()),
            'status': '✅ Operational'
        }


# Singleton instance
_assistant = None

def get_assistant() -> DropshippingAIAssistant:
    """Get singleton AI assistant"""
    global _assistant
    if _assistant is None:
        _assistant = DropshippingAIAssistant()
    return _assistant
