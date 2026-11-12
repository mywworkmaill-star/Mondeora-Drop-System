"""
AI-Powered AliExpress Link Verifier
Her yeni tedarikçi linkini doğrular:
- Link çalışıyor mu?
- Doğru ürüne ait mi?
- Fotoğraflar eşleşiyor mu?
- Fiyat makul mü?
"""

import requests
import json
import os
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dotenv import load_dotenv
import base64
from io import BytesIO
from PIL import Image
import hashlib

load_dotenv()


class AliExpressLinkVerifier:
    """AI tabanlı link doğrulama sistemi"""
    
    def __init__(self):
        self.ebay_token = os.getenv('EBAY_ACCESS_TOKEN')
        self.anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        
    def verify_link_works(self, ali_product_id: str) -> Dict:
        """1. ADIM: Link çalışıyor mu?"""
        
        urls_to_try = [
            f'https://www.aliexpress.com/item/{ali_product_id}.html',
            f'https://aliexpress.com/item/{ali_product_id}.html',
            f'https://www.aliexpress.us/item/{ali_product_id}.html'
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        for url in urls_to_try:
            try:
                response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
                
                if response.status_code == 200:
                    return {
                        'works': True,
                        'working_url': url,
                        'status_code': 200,
                        'error': None
                    }
                elif response.status_code in [403, 429]:
                    # CAPTCHA or rate limit - try next
                    continue
                    
            except Exception as e:
                continue
        
        return {
            'works': False,
            'working_url': None,
            'status_code': 404,
            'error': 'All URLs failed - product might be removed'
        }
    
    def fetch_ebay_product_data(self, ebay_item_id: str) -> Optional[Dict]:
        """eBay'den ürün bilgilerini çek"""
        
        headers = {
            'Authorization': f'Bearer {self.ebay_token}',
            'Content-Type': 'application/json'
        }
        
        # Try multiple eBay APIs
        
        # 1. Try Browse API (public)
        try:
            url = f'https://api.ebay.com/buy/browse/v1/item/v1|{ebay_item_id}|0'
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                return {
                    'title': data.get('title', ''),
                    'price': float(data.get('price', {}).get('value', 0)),
                    'images': [img.get('imageUrl') for img in data.get('image', {}).get('imageUrls', [])[:3]],
                    'description': data.get('shortDescription', ''),
                    'source': 'browse_api'
                }
        except:
            pass
        
        # 2. Try Trading API (legacy but reliable)
        try:
            url = 'https://api.ebay.com/ws/api.dll'
            
            xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
<GetItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    <RequesterCredentials>
        <eBayAuthToken>{self.ebay_token}</eBayAuthToken>
    </RequesterCredentials>
    <ItemID>{ebay_item_id}</ItemID>
    <DetailLevel>ReturnAll</DetailLevel>
</GetItemRequest>"""
            
            headers_xml = {
                'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
                'X-EBAY-API-CALL-NAME': 'GetItem',
                'X-EBAY-API-SITEID': '77',  # Germany
                'Content-Type': 'text/xml'
            }
            
            response = requests.post(url, data=xml_request, headers=headers_xml, timeout=10)
            
            if response.status_code == 200 and 'Title' in response.text:
                # Simple XML parsing (no dependencies)
                text = response.text
                
                title_start = text.find('<Title>') + 7
                title_end = text.find('</Title>')
                title = text[title_start:title_end] if title_start > 6 else ''
                
                price_start = text.find('<CurrentPrice>') + 14
                price_end = text.find('</CurrentPrice>')
                price_text = text[price_start:price_end] if price_start > 13 else '0'
                price = float(price_text.replace(',', '.').split('>')[0]) if price_text else 0
                
                # Extract image URLs
                images = []
                img_start = 0
                while True:
                    img_start = text.find('<PictureURL>', img_start)
                    if img_start == -1:
                        break
                    img_start += 12
                    img_end = text.find('</PictureURL>', img_start)
                    if img_end != -1:
                        images.append(text[img_start:img_end])
                    if len(images) >= 3:
                        break
                
                return {
                    'title': title,
                    'price': price,
                    'images': images[:3],
                    'description': '',
                    'source': 'trading_api'
                }
        except:
            pass
        
        return None
    
    def fetch_aliexpress_product_data(self, ali_product_id: str, ali_api_client=None) -> Optional[Dict]:
        """AliExpress'ten ürün bilgilerini çek"""
        
        # Try AliExpress API first (if available)
        if ali_api_client:
            try:
                result = ali_api_client.get_product_details(ali_product_id)
                
                if result and 'aliexpress_ds_product_get_response' in result:
                    product = result['aliexpress_ds_product_get_response']['result']
                    
                    return {
                        'title': product.get('subject', ''),
                        'price': float(product.get('target_sale_price', 0)),
                        'images': [img.get('image_url') for img in product.get('image_u_r_ls', [])[:3]],
                        'description': product.get('detail', ''),
                        'source': 'aliexpress_api'
                    }
            except:
                pass
        
        # Fallback: scraping (less reliable but works)
        try:
            url = f'https://www.aliexpress.com/item/{ali_product_id}.html'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                html = response.text
                
                # Simple extraction (basic parsing)
                title = ''
                if '"title":"' in html:
                    start = html.find('"title":"') + 9
                    end = html.find('"', start)
                    title = html[start:end].replace('\\u0027', "'").replace('\\/', '/')
                
                price = 0
                if '"actMinPrice":"' in html:
                    start = html.find('"actMinPrice":"') + 15
                    end = html.find('"', start)
                    try:
                        price = float(html[start:end])
                    except:
                        pass
                
                # Extract image URLs
                images = []
                img_pattern = '"imagePathList":['
                if img_pattern in html:
                    start = html.find(img_pattern) + len(img_pattern)
                    end = html.find(']', start)
                    img_json = html[start:end]
                    # Simple JSON array parsing
                    img_urls = [url.strip('"') for url in img_json.split(',')[:3]]
                    images = [f'https:{url}' if not url.startswith('http') else url for url in img_urls]
                
                return {
                    'title': title,
                    'price': price,
                    'images': images,
                    'description': '',
                    'source': 'scraping'
                }
        except:
            pass
        
        return None
    
    def compare_images_ai(self, ebay_images: List[str], ali_images: List[str]) -> Dict:
        """AI ile görsel karşılaştırma (Claude Vision API)"""
        
        if not ebay_images or not ali_images:
            return {
                'match': False,
                'confidence': 0,
                'reason': 'Missing images'
            }
        
        # Basit yöntem: İlk fotoğrafı karşılaştır
        try:
            # Download images
            ebay_img_data = requests.get(ebay_images[0], timeout=10).content
            ali_img_data = requests.get(ali_images[0], timeout=10).content
            
            # Convert to base64
            ebay_b64 = base64.b64encode(ebay_img_data).decode('utf-8')
            ali_b64 = base64.b64encode(ali_img_data).decode('utf-8')
            
            # Call Claude Vision API
            if self.anthropic_key:
                headers = {
                    'x-api-key': self.anthropic_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json'
                }
                
                payload = {
                    'model': 'claude-3-5-sonnet-20241022',
                    'max_tokens': 300,
                    'messages': [{
                        'role': 'user',
                        'content': [
                            {
                                'type': 'image',
                                'source': {
                                    'type': 'base64',
                                    'media_type': 'image/jpeg',
                                    'data': ebay_b64
                                }
                            },
                            {
                                'type': 'image',
                                'source': {
                                    'type': 'base64',
                                    'media_type': 'image/jpeg',
                                    'data': ali_b64
                                }
                            },
                            {
                                'type': 'text',
                                'text': 'Compare these two product images. Are they the SAME product? Answer in JSON format: {"same_product": true/false, "confidence": 0-100, "reason": "brief explanation"}. Be strict - they must be identical products, not just similar.'
                            }
                        ]
                    }]
                }
                
                response = requests.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    text = result['content'][0]['text']
                    
                    # Parse JSON response
                    try:
                        data = json.loads(text)
                        return {
                            'match': data.get('same_product', False),
                            'confidence': data.get('confidence', 0),
                            'reason': data.get('reason', ''),
                            'method': 'claude_vision'
                        }
                    except:
                        # Fallback text parsing
                        if 'true' in text.lower() or 'same' in text.lower():
                            return {
                                'match': True,
                                'confidence': 80,
                                'reason': 'AI confirmed same product',
                                'method': 'claude_vision'
                            }
                        else:
                            return {
                                'match': False,
                                'confidence': 70,
                                'reason': 'AI detected different products',
                                'method': 'claude_vision'
                            }
            
            # Fallback: Hash-based comparison (basic)
            ebay_hash = hashlib.md5(ebay_img_data).hexdigest()
            ali_hash = hashlib.md5(ali_img_data).hexdigest()
            
            if ebay_hash == ali_hash:
                return {
                    'match': True,
                    'confidence': 100,
                    'reason': 'Exact image match (identical files)',
                    'method': 'hash'
                }
            else:
                # Size comparison
                ebay_size = len(ebay_img_data)
                ali_size = len(ali_img_data)
                size_diff = abs(ebay_size - ali_size) / max(ebay_size, ali_size)
                
                if size_diff < 0.1:
                    return {
                        'match': True,
                        'confidence': 70,
                        'reason': 'Similar image size (likely same product)',
                        'method': 'size_comparison'
                    }
                else:
                    return {
                        'match': False,
                        'confidence': 60,
                        'reason': 'Different image sizes (might be different products)',
                        'method': 'size_comparison'
                    }
        
        except Exception as e:
            return {
                'match': None,
                'confidence': 0,
                'reason': f'Image comparison failed: {str(e)}',
                'method': 'error'
            }
    
    def compare_titles(self, ebay_title: str, ali_title: str) -> Dict:
        """Title karşılaştırma (text similarity)"""
        
        if not ebay_title or not ali_title:
            return {
                'match': False,
                'confidence': 0,
                'reason': 'Missing titles'
            }
        
        # Normalize titles
        ebay_clean = ebay_title.lower().strip()
        ali_clean = ali_title.lower().strip()
        
        # Exact match
        if ebay_clean == ali_clean:
            return {
                'match': True,
                'confidence': 100,
                'reason': 'Exact title match'
            }
        
        # Word overlap
        ebay_words = set(ebay_clean.split())
        ali_words = set(ali_clean.split())
        
        # Remove common words
        common_words = {'for', 'with', 'and', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'from', 
                       'für', 'mit', 'und', 'der', 'die', 'das', 'ein', 'eine'}
        ebay_words -= common_words
        ali_words -= common_words
        
        if not ebay_words or not ali_words:
            return {
                'match': False,
                'confidence': 0,
                'reason': 'No meaningful words to compare'
            }
        
        # Jaccard similarity
        intersection = len(ebay_words & ali_words)
        union = len(ebay_words | ali_words)
        similarity = intersection / union if union > 0 else 0
        
        if similarity > 0.6:
            return {
                'match': True,
                'confidence': int(similarity * 100),
                'reason': f'{intersection}/{union} words match'
            }
        else:
            return {
                'match': False,
                'confidence': int(similarity * 100),
                'reason': f'Low word overlap: {intersection}/{union}'
            }
    
    def check_price_sanity(self, ali_price: float, ebay_price: float) -> Dict:
        """Fiyat kontrolü (makul marj var mı?)"""
        
        if ali_price <= 0 or ebay_price <= 0:
            return {
                'sane': False,
                'reason': 'Invalid prices',
                'margin': 0
            }
        
        margin = ((ebay_price - ali_price) / ali_price) * 100
        
        if margin < 20:
            return {
                'sane': False,
                'reason': f'Too low margin: {margin:.1f}% (minimum 20%)',
                'margin': margin
            }
        elif margin > 500:
            return {
                'sane': False,
                'reason': f'Suspiciously high margin: {margin:.1f}% (max 500%)',
                'margin': margin
            }
        else:
            return {
                'sane': True,
                'reason': f'Healthy margin: {margin:.1f}%',
                'margin': margin
            }
    
    def verify_full(
        self,
        ebay_item_id: str,
        ali_product_id: str,
        ali_api_client=None,
        skip_images: bool = False
    ) -> Dict:
        """TAM DOĞRULAMA - tüm kontroller"""
        
        print("=" * 80)
        print(f"🔍 FULL VERIFICATION: eBay {ebay_item_id} ↔ AliExpress {ali_product_id}")
        print("=" * 80)
        print()
        
        result = {
            'verified': False,
            'confidence': 0,
            'checks': {},
            'timestamp': datetime.now().isoformat()
        }
        
        # 1. Link çalışıyor mu?
        print("1️⃣ Checking if AliExpress link works...")
        link_check = self.verify_link_works(ali_product_id)
        result['checks']['link_works'] = link_check
        
        if not link_check['works']:
            print(f"   ❌ Link doesn't work: {link_check['error']}")
            result['confidence'] = 0
            result['verified'] = False
            result['reason'] = 'AliExpress link is broken'
            return result
        
        print(f"   ✅ Link works: {link_check['working_url']}")
        print()
        
        # 2. eBay data
        print("2️⃣ Fetching eBay product data...")
        ebay_data = self.fetch_ebay_product_data(ebay_item_id)
        result['checks']['ebay_data'] = ebay_data
        
        if not ebay_data:
            print("   ⚠️  Could not fetch eBay data")
            result['confidence'] = 20
            result['verified'] = False
            result['reason'] = 'Cannot fetch eBay data for comparison'
            return result
        
        print(f"   ✅ eBay: {ebay_data['title'][:50]}... (€{ebay_data['price']})")
        print()
        
        # 3. AliExpress data
        print("3️⃣ Fetching AliExpress product data...")
        ali_data = self.fetch_aliexpress_product_data(ali_product_id, ali_api_client)
        result['checks']['ali_data'] = ali_data
        
        if not ali_data:
            print("   ⚠️  Could not fetch AliExpress data")
            result['confidence'] = 20
            result['verified'] = False
            result['reason'] = 'Cannot fetch AliExpress data for comparison'
            return result
        
        print(f"   ✅ AliExpress: {ali_data['title'][:50]}... (${ali_data['price']})")
        print()
        
        # 4. Title comparison
        print("4️⃣ Comparing titles...")
        title_result = self.compare_titles(ebay_data['title'], ali_data['title'])
        result['checks']['title_match'] = title_result
        
        if title_result['match']:
            print(f"   ✅ Titles match ({title_result['confidence']}%): {title_result['reason']}")
        else:
            print(f"   ⚠️  Titles don't match ({title_result['confidence']}%): {title_result['reason']}")
        print()
        
        # 5. Image comparison (optional - takes time)
        if not skip_images and ebay_data['images'] and ali_data['images']:
            print("5️⃣ Comparing images with AI...")
            image_result = self.compare_images_ai(ebay_data['images'], ali_data['images'])
            result['checks']['image_match'] = image_result
            
            if image_result['match']:
                print(f"   ✅ Images match ({image_result['confidence']}%): {image_result['reason']}")
            else:
                print(f"   ⚠️  Images don't match ({image_result['confidence']}%): {image_result['reason']}")
            print()
        else:
            print("5️⃣ Skipping image comparison")
            result['checks']['image_match'] = {'match': None, 'confidence': 0, 'reason': 'Skipped'}
            print()
        
        # 6. Price sanity
        print("6️⃣ Checking price sanity...")
        price_result = self.check_price_sanity(ali_data['price'], ebay_data['price'])
        result['checks']['price_sane'] = price_result
        
        if price_result['sane']:
            print(f"   ✅ Price is sane: {price_result['reason']}")
        else:
            print(f"   ⚠️  Price issue: {price_result['reason']}")
        print()
        
        # FINAL SCORE
        print("=" * 80)
        print("📊 FINAL VERIFICATION SCORE")
        print("=" * 80)
        
        score = 0
        max_score = 0
        
        # Link works: 20 points
        if link_check['works']:
            score += 20
        max_score += 20
        
        # Title match: 30 points
        if title_result['match']:
            score += title_result['confidence'] * 0.3
        max_score += 30
        
        # Image match: 30 points (if checked)
        if result['checks']['image_match']['match'] is not None:
            if result['checks']['image_match']['match']:
                score += result['checks']['image_match']['confidence'] * 0.3
            max_score += 30
        
        # Price sane: 20 points
        if price_result['sane']:
            score += 20
        max_score += 20
        
        confidence = int((score / max_score) * 100) if max_score > 0 else 0
        result['confidence'] = confidence
        
        # Decision
        if confidence >= 70:
            result['verified'] = True
            result['reason'] = f'High confidence match ({confidence}%)'
            print(f"✅ VERIFIED! Confidence: {confidence}%")
        elif confidence >= 50:
            result['verified'] = True
            result['reason'] = f'Moderate confidence ({confidence}%) - proceed with caution'
            print(f"⚠️  VERIFIED (with caution). Confidence: {confidence}%")
        else:
            result['verified'] = False
            result['reason'] = f'Low confidence ({confidence}%) - likely wrong product'
            print(f"❌ NOT VERIFIED. Confidence: {confidence}%")
        
        print("=" * 80)
        print()
        
        return result


def main():
    """Test script"""
    verifier = AliExpressLinkVerifier()
    
    # Test case
    ebay_id = "860125870526"
    ali_id = "1005007756879885"
    
    result = verifier.verify_full(
        ebay_item_id=ebay_id,
        ali_product_id=ali_id,
        skip_images=False
    )
    
    print()
    print("=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
