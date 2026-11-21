"""
AI Tools Integration Module
Wraps headroom, composio, agent-reach, and perplexity for Mondeora
"""

import os
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class AIToolsManager:
    """Centralized manager for all AI enhancement tools"""
    
    def __init__(self):
        self.headroom = None
        self.composio = None
        self.agent_reach = None
        self.perplexity = None
        self._initialize_tools()
    
    def _initialize_tools(self):
        """Initialize all AI tools"""
        try:
            # Headroom - Context compression
            from headroom import compress
            self.headroom = compress
            logger.info("✅ Headroom initialized")
        except ImportError as e:
            logger.warning(f"⚠️  Headroom not available: {e}")
        
        try:
            # Composio - 1000+ tools
            from composio import Composio
            self.composio = Composio()
            logger.info("✅ Composio initialized")
        except ImportError as e:
            logger.warning(f"⚠️  Composio not available: {e}")
        
        try:
            # Agent Reach - Internet access
            import agent_reach
            self.agent_reach = agent_reach
            logger.info("✅ Agent Reach initialized")
        except ImportError as e:
            logger.warning(f"⚠️  Agent Reach not available: {e}")
        
        try:
            # Perplexity - AI search
            from perplexity import Perplexity
            api_key = os.getenv('PERPLEXITY_API_KEY')
            if api_key:
                self.perplexity = Perplexity(api_key=api_key)
                logger.info("✅ Perplexity initialized")
            else:
                logger.warning("⚠️  PERPLEXITY_API_KEY not set")
        except ImportError as e:
            logger.warning(f"⚠️  Perplexity not available: {e}")
    
    def compress_context(self, text: str, target_ratio: float = 0.5) -> str:
        """
        Compress large context for AI processing
        
        Args:
            text: Text to compress
            target_ratio: Target compression ratio (0.5 = 50% reduction)
        
        Returns:
            Compressed text
        """
        if not self.headroom:
            return text
        
        try:
            compressed = self.headroom(text, target_ratio=target_ratio)
            logger.info(f"📊 Compressed {len(text)} -> {len(compressed)} chars ({len(compressed)/len(text)*100:.1f}%)")
            return compressed
        except Exception as e:
            logger.error(f"❌ Compression failed: {e}")
            return text
    
    def search_web(self, query: str, max_results: int = 5) -> Optional[Dict]:
        """
        Search web using Perplexity AI
        
        Args:
            query: Search query
            max_results: Maximum results to return
        
        Returns:
            Search results dict
        """
        if not self.perplexity:
            logger.warning("Perplexity not initialized")
            return None
        
        try:
            search = self.perplexity.search.create(
                query=query,
                max_results=max_results
            )
            results = {
                'query': query,
                'results': [
                    {'title': r.title, 'url': r.url, 'snippet': r.snippet}
                    for r in search.results
                ]
            }
            logger.info(f"🔍 Found {len(results['results'])} results for: {query}")
            return results
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return None
    
    def get_available_tools(self) -> List[str]:
        """Get list of available AI tools"""
        tools = []
        if self.headroom:
            tools.append('headroom')
        if self.composio:
            tools.append('composio')
        if self.agent_reach:
            tools.append('agent_reach')
        if self.perplexity:
            tools.append('perplexity')
        return tools


# Singleton instance
_ai_tools = None

def get_ai_tools() -> AIToolsManager:
    """Get singleton AI tools manager"""
    global _ai_tools
    if _ai_tools is None:
        _ai_tools = AIToolsManager()
    return _ai_tools
