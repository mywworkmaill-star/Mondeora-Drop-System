"""
Vision-based Aspect Extraction
Extract eBay aspects from product images using vision AI
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path


class VisionAspectExtractor:
    """
    Extract product aspects from images using vision AI
    
    Features:
    - Material, color, features extraction
    - Confidence scoring (only use >=80%)
    - Cache results (avoid duplicate calls)
    - eBay aspect format output
    """
    
    def __init__(self, db_path='data/dropshipping.db', confidence_threshold=80):
        self.db_path = db_path
        self.confidence_threshold = confidence_threshold
        self._ensure_vision_table()
    
    def _ensure_vision_table(self):
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
    
    def _build_vision_prompt(self, product_type='organizer'):
        """Build structured vision prompt"""
        
        base_prompt = f"""
Analyze this {product_type} product image and extract information:

1. MATERIAL: What material(s) is it made of?
   Options: Kunststoff (plastic), Metall (metal), Stoff (fabric), 
   Holz (wood), Silikon (silicone), Edelstahl (stainless steel)
   Be specific. If multiple, list main material first.

2. COLOR: What color(s) are visible?
   Use German names: Schwarz, Weiß, Grau, Blau, Rot, Grün, 
   Gelb, Rosa, Lila, Braun, Orange, Transparent, Mehrfarbig
   List main color first, then additional colors.

3. FEATURES: What key features do you see?
   - Compartment/pocket count (e.g., "3 Fächer")
   - Mounting type (Selbstklebend, Wandmontage, Freistehend, Saugnapf)
   - Mechanisms (Faltbar, Stapelbar, Drehbar, Ausziehbar)
   - Closures (Reißverschluss, Klettverschluss, Druckknopf, Magnetisch)
   - Surface (Rutschfest, Wasserdicht, Transparent)

4. SIZE: Estimate size category
   Klein (<20cm), Mittel (20-40cm), Groß (>40cm)
   Only estimate if clearly visible.

5. CONFIDENCE: Rate confidence for each answer (0-100)
   100 = absolutely certain
   80-99 = very confident
   60-79 = somewhat confident
   <60 = uncertain

IMPORTANT: Respond ONLY with valid JSON in this exact format:
{{
  "material": {{"value": "Material name", "confidence": 95}},
  "color": {{"value": ["Main color", "Secondary color"], "confidence": 90}},
  "features": {{"value": ["Feature 1", "Feature 2"], "confidence": 85}},
  "size": {{"value": "Size category", "confidence": 70}}
}}

If you cannot determine something, use "Unbekannt" with confidence 0.
"""
        return base_prompt
    
    def _parse_vision_response(self, raw_response: str) -> Dict:
        """Parse vision JSON response"""
        try:
            # Try to parse as JSON
            data = json.loads(raw_response)
            return data
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if '```json' in raw_response:
                json_str = raw_response.split('```json')[1].split('```')[0].strip()
                return json.loads(json_str)
            elif '```' in raw_response:
                json_str = raw_response.split('```')[1].split('```')[0].strip()
                return json.loads(json_str)
            else:
                raise ValueError(f"Could not parse vision response: {raw_response[:200]}")
    
    def _convert_to_ebay_aspects(self, vision_data: Dict) -> Dict:
        """Convert vision data to eBay aspect format"""
        
        aspects = {}
        low_confidence = {}
        total_confidence = 0
        count = 0
        
        # Material
        if 'material' in vision_data:
            mat = vision_data['material']
            if mat['confidence'] >= self.confidence_threshold and mat['value'] != 'Unbekannt':
                aspects['Material'] = [mat['value']]
                total_confidence += mat['confidence']
                count += 1
            else:
                low_confidence['material'] = mat
        
        # Color (Farbe)
        if 'color' in vision_data:
            col = vision_data['color']
            if col['confidence'] >= self.confidence_threshold and col['value']:
                # value can be string or list
                if isinstance(col['value'], str):
                    aspects['Farbe'] = [col['value']]
                else:
                    aspects['Farbe'] = col['value']
                total_confidence += col['confidence']
                count += 1
            else:
                low_confidence['color'] = col
        
        # Features (Besonderheiten)
        if 'features' in vision_data:
            feat = vision_data['features']
            if feat['confidence'] >= self.confidence_threshold and feat['value']:
                if isinstance(feat['value'], str):
                    aspects['Besonderheiten'] = [feat['value']]
                else:
                    aspects['Besonderheiten'] = feat['value']
                total_confidence += feat['confidence']
                count += 1
            else:
                low_confidence['features'] = feat
        
        # Size (optional, usually low confidence)
        if 'size' in vision_data:
            size = vision_data['size']
            if size['confidence'] >= self.confidence_threshold and size['value'] != 'Unbekannt':
                aspects['Größe'] = [size['value']]
                total_confidence += size['confidence']
                count += 1
            else:
                low_confidence['size'] = size
        
        avg_confidence = int(total_confidence / count) if count > 0 else 0
        
        return {
            'aspects': aspects,
            'low_confidence': low_confidence,
            'confidence_score': avg_confidence
        }
    
    def analyze_product(
        self, 
        product_id: int,
        image_url: str,
        product_type: str = 'organizer',
        force_refresh: bool = False
    ) -> Dict:
        """
        Analyze product image and extract aspects
        
        Args:
            product_id: Database product ID
            image_url: Product main image URL
            product_type: Type hint for better prompts
            force_refresh: Skip cache and analyze again
        
        Returns:
            {
                'product_id': int,
                'analyzed_at': str,
                'image_url': str,
                'raw_response': str,
                'aspects': dict,  # eBay format
                'low_confidence': dict,
                'confidence_score': int,
                'status': str
            }
        """
        
        # Check cache first
        if not force_refresh:
            cached = self._get_cached(product_id, image_url)
            if cached:
                return cached
        
        print(f"🔍 Analyzing product {product_id} with vision AI...")
        
        try:
            # Build prompt
            prompt = self._build_vision_prompt(product_type)
            
            # Call vision using execute_code with hermes_tools
            import subprocess, json as _json
            # 🚨 SECURITY FIX (2026-11-21): image_url/prompt used to be
            # f-string-embedded directly into generated Python SOURCE CODE
            # then run via `python -c` — a crafted AliExpress image URL
            # containing a quote + Python syntax (e.g. "x');import
            # os;os.system('...')#") would break out of the string literal
            # and execute arbitrary code. json.dumps() produces a properly
            # escaped Python/JSON string literal, closing the injection.
            safe_image_url = _json.dumps(image_url)
            safe_prompt = _json.dumps(prompt)
            vision_code = f"""
from hermes_tools import vision_analyze
result = vision_analyze({safe_image_url}, {safe_prompt})
print(result['content'])
"""
            
            result = subprocess.run(
                ['python', '-c', vision_code],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise Exception(f"Vision call failed: {result.stderr}")
            
            raw_response = result.stdout.strip()
            
            # Parse response
            vision_data = self._parse_vision_response(raw_response)
            
            # Convert to eBay format
            result = self._convert_to_ebay_aspects(vision_data)
            
            # Build full result
            full_result = {
                'product_id': product_id,
                'analyzed_at': datetime.now().isoformat(),
                'image_url': image_url,
                'raw_response': raw_response,
                'aspects': result['aspects'],
                'low_confidence': result['low_confidence'],
                'confidence_score': result['confidence_score'],
                'status': 'success'
            }
            
            # Cache it
            self._save_to_cache(full_result)
            
            return full_result
            
        except Exception as e:
            print(f"❌ Vision analysis failed: {e}")
            
            error_result = {
                'product_id': product_id,
                'analyzed_at': datetime.now().isoformat(),
                'image_url': image_url,
                'raw_response': str(e),
                'aspects': {},
                'low_confidence': {},
                'confidence_score': 0,
                'status': 'failed'
            }
            
            # Cache failure too (avoid retrying immediately)
            self._save_to_cache(error_result)
            
            return error_result
    
    def _get_cached(self, product_id: int, image_url: str) -> Optional[Dict]:
        """Get cached vision analysis if recent (<7 days)"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get most recent analysis
        cursor.execute('''
            SELECT analyzed_at, raw_response, aspects_json, confidence_score, status
            FROM vision_analysis
            WHERE product_id = ? AND image_url = ?
            ORDER BY analyzed_at DESC
            LIMIT 1
        ''', (product_id, image_url))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        analyzed_at, raw_response, aspects_json, confidence, status = row
        
        # Check if too old (>7 days)
        analyzed_time = datetime.fromisoformat(analyzed_at)
        if datetime.now() - analyzed_time > timedelta(days=7):
            return None
        
        # Parse aspects JSON
        aspects_data = json.loads(aspects_json) if aspects_json else {}
        
        print(f"   ✅ Cache hit (analyzed {analyzed_at})")
        
        return {
            'product_id': product_id,
            'analyzed_at': analyzed_at,
            'image_url': image_url,
            'raw_response': raw_response,
            'aspects': aspects_data.get('aspects', {}),
            'low_confidence': aspects_data.get('low_confidence', {}),
            'confidence_score': confidence,
            'status': status
        }
    
    def _save_to_cache(self, result: Dict):
        """Save vision analysis to cache"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Prepare aspects JSON
        aspects_data = {
            'aspects': result['aspects'],
            'low_confidence': result['low_confidence']
        }
        
        # Insert or replace
        cursor.execute('''
            INSERT OR REPLACE INTO vision_analysis
            (product_id, image_url, analyzed_at, raw_response, 
             aspects_json, confidence_score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            result['product_id'],
            result['image_url'],
            result['analyzed_at'],
            result['raw_response'],
            json.dumps(aspects_data, ensure_ascii=False),
            result['confidence_score'],
            result['status']
        ))
        
        conn.commit()
        conn.close()
    
    def get_cached_or_analyze(
        self,
        product_id: int,
        image_url: str,
        product_type: str = 'organizer'
    ) -> Dict:
        """Get from cache (vision calls must be done externally)"""
        
        # Check cache
        cached = self._get_cached(product_id, image_url)
        if cached:
            return cached
        
        # No cache: return empty (vision must be called externally)
        print(f"   ⚠️  No vision cache for product {product_id}")
        print(f"   → Run vision analysis manually first")
        
        return {
            'product_id': product_id,
            'analyzed_at': datetime.now().isoformat(),
            'image_url': image_url,
            'raw_response': '',
            'aspects': {},
            'low_confidence': {},
            'confidence_score': 0,
            'status': 'not_analyzed'
        }


def main():
    """Test vision extractor"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.vision.aspect_extractor <product_id>")
        sys.exit(1)
    
    product_id = int(sys.argv[1])
    
    # Get product from database
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, image_url FROM products WHERE id = ?', (product_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print(f"❌ Product {product_id} not found")
        sys.exit(1)
    
    pid, title, image_url = row
    
    print(f"\n{'='*80}")
    print(f"VISION ASPECT EXTRACTION TEST")
    print(f"{'='*80}")
    print(f"\nProduct ID: {pid}")
    print(f"Title: {title[:60]}...")
    print(f"Image: {image_url[:60]}...")
    
    # Analyze
    extractor = VisionAspectExtractor()
    result = extractor.analyze_product(pid, image_url)
    
    # Display results
    print(f"\n{'='*80}")
    print(f"RESULTS")
    print(f"{'='*80}")
    print(f"\nStatus: {result['status']}")
    print(f"Confidence: {result['confidence_score']}%")
    
    if result['aspects']:
        print(f"\n✅ High Confidence Aspects (>={extractor.confidence_threshold}%):")
        for key, value in result['aspects'].items():
            print(f"   {key}: {value}")
    
    if result['low_confidence']:
        print(f"\n⚠️  Low Confidence (<{extractor.confidence_threshold}%):")
        for key, data in result['low_confidence'].items():
            print(f"   {key}: {data['value']} ({data['confidence']}%)")
    
    print(f"\n{'='*80}")


if __name__ == '__main__':
    main()
