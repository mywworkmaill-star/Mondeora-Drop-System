"""
Vision aspect extraction helper for Hermes context
Calls vision_analyze directly instead of subprocess
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict


class VisionCache:
    """Simple vision cache without subprocess dependency"""
    
    def __init__(self, db_path='data/dropshipping.db'):
        self.db_path = db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create vision_analysis table if not exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vision_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                image_url TEXT,
                analyzed_at DATETIME,
                raw_response TEXT,
                aspects_json TEXT,
                confidence_score INTEGER,
                status VARCHAR(20),
                UNIQUE(product_id, image_url)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_cached(self, product_id: int, image_url: str) -> Dict:
        """Get cached vision result"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT aspects_json, confidence_score, analyzed_at
            FROM vision_analysis
            WHERE product_id = ? AND image_url = ?
            ORDER BY analyzed_at DESC
            LIMIT 1
        ''', (product_id, image_url))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        aspects_json, confidence, analyzed_at = row
        aspects_data = json.loads(aspects_json) if aspects_json else {}
        
        return {
            'product_id': product_id,
            'aspects': aspects_data.get('aspects', {}),
            'confidence_score': confidence,
            'analyzed_at': analyzed_at,
            'status': 'success'
        }
    
    def save(self, product_id: int, image_url: str, aspects: Dict, confidence: int, raw_response: str = ""):
        """Save vision result to cache"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        aspects_data = {'aspects': aspects, 'low_confidence': {}}
        
        cursor.execute('''
            INSERT OR REPLACE INTO vision_analysis
            (product_id, image_url, analyzed_at, raw_response, 
             aspects_json, confidence_score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            product_id,
            image_url,
            datetime.now().isoformat(),
            raw_response[:1000],  # Limit
            json.dumps(aspects_data, ensure_ascii=False),
            confidence,
            'success'
        ))
        
        conn.commit()
        conn.close()


def parse_vision_json(raw_text: str) -> Dict:
    """Parse vision response (JSON or markdown)"""
    try:
        # Direct JSON
        return json.loads(raw_text)
    except:
        # Try extracting from markdown
        if '```json' in raw_text:
            json_str = raw_text.split('```json')[1].split('```')[0].strip()
            return json.loads(json_str)
        elif '```' in raw_text:
            json_str = raw_text.split('```')[1].split('```')[0].strip()
            return json.loads(json_str)
        else:
            raise ValueError(f"Could not parse: {raw_text[:200]}")


def convert_to_ebay_aspects(vision_data: Dict, threshold: int = 80) -> tuple:
    """Convert vision data to eBay format"""
    
    aspects = {}
    total_confidence = 0
    count = 0
    
    # Material
    if 'material' in vision_data:
        mat = vision_data['material']
        if mat['confidence'] >= threshold and mat['value'] != 'Unbekannt':
            aspects['Material'] = [mat['value']]
            total_confidence += mat['confidence']
            count += 1
    
    # Color
    if 'color' in vision_data:
        col = vision_data['color']
        if col['confidence'] >= threshold:
            if isinstance(col['value'], str):
                aspects['Farbe'] = [col['value']]
            else:
                aspects['Farbe'] = col['value']
            total_confidence += col['confidence']
            count += 1
    
    # Features
    if 'features' in vision_data:
        feat = vision_data['features']
        if feat['confidence'] >= threshold:
            if isinstance(feat['value'], str):
                aspects['Besonderheiten'] = [feat['value']]
            else:
                aspects['Besonderheiten'] = feat['value']
            total_confidence += feat['confidence']
            count += 1
    
    avg_confidence = int(total_confidence / count) if count > 0 else 0
    
    return aspects, avg_confidence


# Global cache instance
_cache = None

def get_cache():
    """Get or create cache instance"""
    global _cache
    if _cache is None:
        _cache = VisionCache()
    return _cache
