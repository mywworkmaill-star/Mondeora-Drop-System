"""
Agency Agents Integration for Mondeora
Provides access to 283 specialist agents
"""

import os
import json
import logging
from typing import Optional, Dict, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class AgencyAgentsManager:
    """Manager for Agency Agents integration"""
    
    def __init__(self):
        self.agents_data_path = self._find_agents_data()
        self.agents_cache = None
        self._load_agents()
    
    def _find_agents_data(self) -> Optional[Path]:
        """Find Agency Agents data file"""
        # Try Hermes plugin location
        hermes_path = Path(os.getenv('LOCALAPPDATA', '')) / 'hermes' / 'plugins' / 'agency-agents-router' / 'data' / 'agents.json'
        if hermes_path.exists():
            return hermes_path
        
        # Try Desktop location
        desktop_path = Path.home() / 'Desktop' / 'agency-agents' / 'integrations' / 'hermes' / 'agency-agents-router' / 'data' / 'agents.json'
        if desktop_path.exists():
            return desktop_path
        
        logger.warning("⚠️  Agency Agents data file not found")
        return None
    
    def _load_agents(self):
        """Load agents data from JSON"""
        if not self.agents_data_path:
            return
        
        try:
            with open(self.agents_data_path, 'r', encoding='utf-8') as f:
                self.agents_cache = json.load(f)
            logger.info(f"✅ Loaded {len(self.agents_cache)} Agency Agents")
        except Exception as e:
            logger.error(f"❌ Failed to load agents: {e}")
            self.agents_cache = []
    
    def search_agents(self, query: str, division: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """
        Search for agents by keyword
        
        Args:
            query: Search query
            division: Filter by division (e.g. 'marketing', 'engineering')
            limit: Maximum results
        
        Returns:
            List of matching agents
        """
        if not self.agents_cache:
            return []
        
        query_lower = query.lower()
        results = []
        
        for agent in self.agents_cache:
            # Check division filter
            if division and agent.get('division') != division:
                continue
            
            # Search in name, description, and body
            search_text = f"{agent.get('name', '')} {agent.get('description', '')} {agent.get('body', '')}".lower()
            
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
        
        logger.info(f"🔍 Found {len(results)} agents for query: {query}")
        return results
    
    def get_agent(self, slug: str) -> Optional[Dict]:
        """Get agent by slug"""
        if not self.agents_cache:
            return None
        
        for agent in self.agents_cache:
            if agent.get('slug') == slug:
                return agent
        
        return None
    
    def get_dropshipping_specialists(self) -> List[Dict]:
        """Get agents specialized in dropshipping/e-commerce"""
        specialists = self.search_agents('e-commerce', limit=20)
        specialists += self.search_agents('dropshipping', limit=20)
        specialists += self.search_agents('marketing', limit=20)
        specialists += self.search_agents('automation', limit=20)
        
        # Deduplicate by slug
        seen = set()
        unique = []
        for agent in specialists:
            if agent['slug'] not in seen:
                seen.add(agent['slug'])
                unique.append(agent)
        
        return unique[:10]  # Return top 10


# Singleton instance
_agency_manager = None

def get_agency_manager() -> AgencyAgentsManager:
    """Get singleton Agency Agents manager"""
    global _agency_manager
    if _agency_manager is None:
        _agency_manager = AgencyAgentsManager()
    return _agency_manager


# Pre-selected specialists for Mondeora
MONDEORA_SPECIALISTS = {
    'cross_border': 'cross-border-e-commerce-specialist',
    'china_ecommerce': 'china-e-commerce-operator',
    'automation': 'automation-governance-architect',
}
