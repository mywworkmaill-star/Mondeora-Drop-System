"""
Upgraded pre_listing_vision.py - Analyzes ALL 6 product images, not just first.

CRITICAL FIX:
- Old code: Only analyzed image 1/6
- New code: Loops through ALL images, prioritizes dimension overlays (images 3-5)
- Stops when dimensions found (cost optimization)
- Example: ID 157 image 4/6 has "17cm×8.5cm" text → now detectable

Cost: $0.02/image analyzed (not per product)
Average: $0.04-0.06 per product (usually find dimensions in image 3-4)
Max: $0.12 per product if all 6 images checked
"""

import sys
sys.path.insert(0, 'src')
import sqlite3
import json
import re
from datetime import datetime

def parse_vision_json(text):
    """Parse vision_analyze response (JSON or markdown)."""
    # Try JSON first
    try:
        if '{' in text:
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            json_str = text[json_start:json_end]
            return json.loads(json_str)
    except:
        pass
    
    # Fallback: Empty dict
    return {}

def has_dimensions(vision_result):
    """Check if vision result contains dimension information."""
    text_lower = str(vision_result).lower()
    
    # Check for dimension keywords
    if any(kw in text_lower for kw in ['cm', 'inch', 'dimension', 'size', 'länge', 'breite', 'höhe']):
        # Check if contains numbers
        if re.search(r'\d+', text_lower):
            return True
    
    return False

def extract_dimensions_from_vision(vision_result):
    """Extract dimension measurements from vision analysis."""
    dimensions = {}
    
    text = str(vision_result)
    
    # Pattern 1: "17cm × 8.5cm"
    match = re.search(r'(\d+(?:\.\d+)?)\s*cm\s*[×x]\s*(\d+(?:\.\d+)?)\s*cm', text, re.IGNORECASE)
    if match:
        dimensions['Länge'] = [f"{match.group(1)} cm"]
        dimensions['Höhe'] = [f"{match.group(2)} cm"]
        return dimensions
    
    # Pattern 2: "Length: 17 cm"
    patterns = {
        'Länge': [r'length[:\s]+(\d+(?:\.\d+)?)\s*cm', r'länge[:\s]+(\d+(?:\.\d+)?)\s*cm'],
        'Breite': [r'width[:\s]+(\d+(?:\.\d+)?)\s*cm', r'breite[:\s]+(\d+(?:\.\d+)?)\s*cm'],
        'Höhe': [r'height[:\s]+(\d+(?:\.\d+)?)\s*cm', r'höhe[:\s]+(\d+(?:\.\d+)?)\s*cm']
    }
    
    for dim_name, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                dimensions[dim_name] = [f"{match.group(1)} cm"]
                break
    
    return dimensions if dimensions else None

def analyze_all_images(product_id, images_csv, hermes_vision_function):
    """
    Analyze ALL images for a product, prioritizing dimension overlays.
    
    Args:
        product_id: Database product ID
        images_csv: Comma-separated image URLs
        hermes_vision_function: vision_analyze tool (callable in Hermes context)
    
    Returns:
        dict with material, color, features, dimensions, confidence
    """
    
    if not images_csv:
        return {'error': 'no_images', 'aspects': {}, 'dimensions': None}
    
    # Split images
    images = [img.strip() for img in images_csv.split(',') if img.strip()]
    
    if not images:
        return {'error': 'no_images', 'aspects': {}, 'dimensions': None}
    
    print(f'📸 Product {product_id} has {len(images)} images')
    print()
    
    # Prioritize image order: Usually dimensions in images 3-5
    # Try order: 4, 3, 5, 2, 6, 1 (most likely to have dimensions first)
    priority_indices = [3, 2, 4, 1, 5, 0] if len(images) >= 4 else list(range(len(images)))
    
    material_result = None
    color_result = None
    features_result = None
    dimensions_result = None
    
    images_analyzed = 0
    max_images = 6  # Safety limit
    
    for idx in priority_indices:
        if idx >= len(images):
            continue
        
        if images_analyzed >= max_images:
            break
        
        img_url = images[idx]
        img_num = idx + 1
        
        print(f'🔍 Analyzing image {img_num}/{len(images)}...')
        print(f'   URL: {img_url[:60]}...')
        
        # Check if this is likely a dimension overlay (heuristic: shorter filename)
        is_likely_dimension = idx >= 2  # Images 3+ often have specs
        
        # Build prompt
        if not dimensions_result and is_likely_dimension:
            # Prioritize dimension extraction
            prompt = f"""Analyze this product image SPECIFICALLY for DIMENSIONS:

1. Are there any measurements written on the image? (cm, inch, dimensions)
2. Look for text overlays with measurements (e.g., "17cm × 8.5cm")
3. If measurements found, extract ALL:
   - Length/Länge (cm and/or inch)
   - Width/Breite (cm and/or inch)
   - Height/Höhe (cm and/or inch)

Also identify:
4. Material: Kunststoff, Metall, Holz, etc.
5. Color: Main colors visible
6. Features: Key product features

Format response as JSON:
{{
  "dimensions_found": true/false,
  "length_cm": "17",
  "height_cm": "8.5",
  "width_cm": "4.5",
  "material": {{"value": "Kunststoff", "confidence": 95}},
  "color": {{"value": ["Transparent"], "confidence": 90}},
  "features": {{"value": ["7 Fächer"], "confidence": 85}}
}}
"""
        else:
            # Standard material/color/features prompt
            prompt = f"""Analyze this product image:

1. MATERIAL: What is it made of? (Kunststoff, Metall, Holz, Silikon, etc.)
2. COLOR: What colors are visible? (German names)
3. FEATURES: Key features (compartments, mounting type, etc.)
4. DIMENSIONS: Any measurements visible in image?

Format as JSON:
{{
  "material": {{"value": "Kunststoff", "confidence": 95}},
  "color": {{"value": ["Weiß"], "confidence": 90}},
  "features": {{"value": ["Selbstklebend"], "confidence": 85}},
  "dimensions_found": false
}}
"""
        
        try:
            # Call vision_analyze (must be in Hermes context!)
            result = hermes_vision_function(img_url, prompt)
            
            images_analyzed += 1
            
            # Parse result
            vision_data = parse_vision_json(result)
            
            # Extract material/color/features (if not yet found)
            if not material_result and 'material' in vision_data:
                material_result = vision_data['material']
            
            if not color_result and 'color' in vision_data:
                color_result = vision_data['color']
            
            if not features_result and 'features' in vision_data:
                features_result = vision_data['features']
            
            # Extract dimensions
            if has_dimensions(result):
                dims = extract_dimensions_from_vision(result)
                if dims:
                    dimensions_result = dims
                    print(f'   ✅ DIMENSIONS FOUND: {dims}')
                    print(f'   💰 Cost so far: ${images_analyzed * 0.02:.2f}')
                    # STOP - we found dimensions!
                    break
                else:
                    print(f'   ⚠️  Dimension keywords found but couldn\'t extract values')
            else:
                print(f'   ℹ️  No dimensions in this image')
        
        except Exception as e:
            print(f'   ❌ Error analyzing image {img_num}: {str(e)[:50]}')
            continue
    
    print()
    print(f'📊 Analysis complete: {images_analyzed}/{len(images)} images analyzed')
    print(f'💰 Total cost: ${images_analyzed * 0.02:.2f}')
    print()
    
    # Build result
    aspects = {}
    confidence_scores = []
    
    if material_result:
        mat_conf = material_result.get('confidence', 0)
        if mat_conf >= 80:
            aspects['Material'] = [material_result['value']]
            confidence_scores.append(mat_conf)
            print(f'✅ Material: {material_result["value"]} ({mat_conf}% confidence)')
    
    if color_result:
        col_conf = color_result.get('confidence', 0)
        if col_conf >= 80:
            colors = color_result['value']
            if isinstance(colors, list):
                aspects['Farbe'] = colors
            else:
                aspects['Farbe'] = [colors]
            confidence_scores.append(col_conf)
            print(f'✅ Farbe: {aspects["Farbe"]} ({col_conf}% confidence)')
    
    if features_result:
        feat_conf = features_result.get('confidence', 0)
        if feat_conf >= 80:
            features = features_result['value']
            if isinstance(features, list):
                aspects['Besonderheiten'] = features[:5]  # Limit to 5
            else:
                aspects['Besonderheiten'] = [features]
            confidence_scores.append(feat_conf)
            print(f'✅ Features: {aspects["Besonderheiten"]} ({feat_conf}% confidence)')
    
    if dimensions_result:
        aspects.update(dimensions_result)
        print(f'✅ Dimensions: {dimensions_result}')
        confidence_scores.append(90)  # High confidence if extracted from text overlay
    
    avg_confidence = int(sum(confidence_scores) / len(confidence_scores)) if confidence_scores else 0
    
    print(f'📈 Overall confidence: {avg_confidence}%')
    print()
    
    return {
        'product_id': product_id,
        'analyzed_at': datetime.now().isoformat(),
        'images_analyzed': images_analyzed,
        'cost': round(images_analyzed * 0.02, 2),
        'aspects': aspects,
        'dimensions': dimensions_result,
        'confidence_score': avg_confidence,
        'status': 'success' if aspects else 'low_confidence'
    }

# Example usage (must be called from Hermes context)
if __name__ == '__main__':
    print('⚠️  This script provides analyze_all_images() function.')
    print('    Must be called from Hermes agent with vision_analyze tool access.')
    print()
    print('Usage:')
    print('  from pre_listing_vision_v2 import analyze_all_images')
    print('  result = analyze_all_images(product_id, images_csv, vision_analyze)')
