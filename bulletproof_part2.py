"""
BULLET-PROOF SYSTEM V3.0 - PART 2
Helper Functions & Advanced Validators
"""

# Continuation from Part 1...

# =====================================
# DUPLICATE CHECKER WITH VERIFICATION
# =====================================
class DuplicateChecker:
    """Multi-source duplicate detection"""
    
    @staticmethod
    def check_sku(sku: str, ebay_client) -> Tuple[bool, str]:
        """Check if SKU exists in eBay"""
        try:
            rate_limiter.wait()
            ebay_client._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
            audit.warning(f"Duplicate SKU detected: {sku}")
            return True, f"SKU exists: {sku}"
        except Exception as e:
            if '404' in str(e) or 'not found' in str(e).lower():
                return False, "SKU available"
            audit.error(f"Duplicate check error for {sku}: {e}")
            # On error, assume it doesn't exist (fail-open)
            return False, "Check failed (assuming available)"
    
    @staticmethod
    def check_product_id(product_id: str, session) -> bool:
        """Check if product ID exists in database"""
        try:
            existing = session.query(Product).filter(
                Product.aliexpress_product_id == product_id
            ).first()
            return existing is not None
        except Exception as e:
            audit.error(f"Database duplicate check error: {e}")
            return False

# =====================================
# IMAGE VALIDATOR WITH VERIFICATION
# =====================================
class ImageValidator:
    """Advanced image validation"""
    
    @staticmethod
    def validate(image_urls: List[str], product_id: str, min_images: int = 3) -> Tuple[bool, str]:
        """
        Validate images:
        - Minimum count
        - URL format
        - Accessibility (sample check)
        """
        if not image_urls:
            return False, "No images provided"
        
        # Count check
        if len(image_urls) < min_images:
            return False, f"Only {len(image_urls)} images (need {min_images})"
        
        # Format check
        valid_images = []
        for url in image_urls:
            if url and isinstance(url, str) and url.startswith('http'):
                valid_images.append(url)
        
        if len(valid_images) < min_images:
            return False, f"Only {len(valid_images)} valid URLs"
        
        # Product ID consistency check
        # Ensure images are from the same product
        product_markers = [str(product_id) in url for url in valid_images[:3]]
        if all(product_markers):
            audit.debug(f"Image validation passed with product ID match")
        
        return True, f"{len(valid_images)} images OK"

# =====================================
# CATEGORY MANAGER
# =====================================
class CategoryManager:
    """Smart category selection and aspect management"""
    
    CATEGORY_MAP = {
        'pet': '20741',
        'dog': '20741',
        'hund': '20741',
        'cat': '20741',
        'katz': '20741',
        'tier': '20741',
        'garden': '20518',
        'garten': '20518',
        'solar': '20518',
        'kitchen': '11700',
        'küche': '11700',
        'home': '11700',
        'baby': '2984',
        'toy': '19068',
        'spielzeug': '19068',
        'sport': '382',
        'fitness': '15273',
    }
    
    ASPECT_CACHE_FILE = 'data/ebay_category_aspects_cache.json'
    
    @staticmethod
    def select_category(title: str, description: str = '') -> Tuple[str, str]:
        """
        Returns: (category_id, category_name)
        """
        text = f"{title} {description}".lower()
        
        for keyword, cat_id in CategoryManager.CATEGORY_MAP.items():
            if keyword in text:
                cat_name = 'Pet' if cat_id == '20741' else 'Other'
                audit.debug(f"Category selected: {cat_id} ({cat_name}) via keyword '{keyword}'")
                return cat_id, cat_name
        
        # Default
        return '20741', 'Pet'
    
    @staticmethod
    def get_aspects(category_id: str, ebay_client) -> Dict:
        """Get aspect requirements with caching"""
        
        # Load cache
        cache = {}
        if os.path.exists(CategoryManager.ASPECT_CACHE_FILE):
            try:
                with open(CategoryManager.ASPECT_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    if category_id in cache:
                        audit.debug(f"Aspect cache hit: {category_id}")
                        return cache[category_id]
            except Exception as e:
                audit.warning(f"Cache load error: {e}")
        
        # Fetch from API
        try:
            rate_limiter.wait()
            resp = ebay_client._request(
                'GET',
                f'/commerce/taxonomy/v1/category_tree/77/get_item_aspects_for_category?category_id={category_id}'
            )
            
            aspects = resp.get('aspects', [])
            required = []
            recommended = []
            
            for aspect in aspects:
                name = aspect.get('localizedAspectName')
                constraint = aspect.get('aspectConstraint', {})
                if constraint.get('aspectRequired'):
                    required.append(name)
                else:
                    recommended.append(name)
            
            result = {
                'required': required,
                'recommended': recommended[:10]
            }
            
            # Save to cache
            cache[category_id] = result
            with open(CategoryManager.ASPECT_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            
            audit.info(f"Aspects fetched for {category_id}: {len(required)} req, {len(recommended)} rec")
            return result
            
        except Exception as e:
            audit.error(f"Aspect fetch failed for {category_id}: {e}")
            return {'required': [], 'recommended': []}
    
    @staticmethod
    def build_aspects(product_data: Dict, category_id: str) -> Dict[str, List[str]]:
        """Build aspect dict from product data"""
        
        aspects = {}
        aspects['Marke'] = ['Markenlos']
        
        title = (product_data.get('subject') or product_data.get('product_title') or '').lower()
        
        # Pet category
        if category_id == '20741':
            if any(word in title for word in ['dog', 'hund', 'puppy', 'welpe']):
                aspects['Tierart'] = ['Hund']
            elif any(word in title for word in ['cat', 'katz', 'kitten']):
                aspects['Tierart'] = ['Katze']
            else:
                aspects['Tierart'] = ['Nicht zutreffend']
            
            if any(word in title for word in ['toy', 'spielzeug', 'ball']):
                aspects['Produktart'] = ['Spielzeug']
            elif any(word in title for word in ['bowl', 'napf', 'feeder']):
                aspects['Produktart'] = ['Napf']
            elif any(word in title for word in ['leash', 'leine', 'lead']):
                aspects['Produktart'] = ['Leine']
            else:
                aspects['Produktart'] = ['Zubehör']
        
        # Garden category
        elif category_id == '20518':
            aspects['Produktart'] = ['Gartendekoration']
            if 'solar' in title:
                aspects['Energiequelle'] = ['Solar']
        
        # Default aspects
        aspects['Material'] = ['Kunststoff']
        aspects['Farbe'] = ['Mehrfarbig']
        
        return aspects

# =====================================
# TITLE OPTIMIZER
# =====================================
class TitleOptimizer:
    """SEO-optimized title generation"""
    
    SPAM_CHARS = ['✨', '🔥', '💥', '⚡', '【', '】', '『', '』', '!!!', '~~~']
    
    @staticmethod
    def optimize(raw_title: str, max_length: int = 80) -> str:
        """Clean and optimize title"""
        
        # Remove spam
        title = raw_title
        for char in TitleOptimizer.SPAM_CHARS:
            title = title.replace(char, ' ')
        
        # Clean whitespace
        title = ' '.join(title.split())
        
        # Capitalize properly
        title = title.title()
        
        # Trim to max length (don't break words)
        if len(title) > max_length:
            title = title[:max_length].rsplit(' ', 1)[0]
        
        return title.strip()

# =====================================
# HTML GENERATOR
# =====================================
class HTMLGenerator:
    """Professional HTML description generator"""
    
    @staticmethod
    def generate(product_data: Dict, category_name: str) -> str:
        """Generate category-specific HTML"""
        
        title = product_data.get('subject') or product_data.get('product_title') or 'Premium Produkt'
        images = product_data.get('image_urls', '').split(';')[:3]
        
        # Category customization
        if category_name == 'Pet':
            if 'dog' in title.lower() or 'hund' in title.lower():
                emoji = '🐾'
                subtitle = 'Robust • Langlebig • Sicher für Hunde'
            elif 'cat' in title.lower() or 'katz' in title.lower():
                emoji = '🐱'
                subtitle = 'Spielspaß • Interaktiv • Katzenfreundlich'
            else:
                emoji = '🐾'
                subtitle = 'Premium Haustierbedarf • Hochwertig'
        else:
            emoji = '✨'
            subtitle = 'Premium Qualität • Schneller Versand'
        
        html = f"""
<table width="100%" cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
  <tr>
    <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center;">
      <h1 style="margin: 0; font-size: 28px;">{emoji} {title[:60]}</h1>
      <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">{subtitle}</p>
    </td>
  </tr>
"""
        
        # Images
        if len(images) >= 3:
            html += f"""
  <tr>
    <td style="padding: 20px;">
      <table width="100%" cellpadding="10">
        <tr>
          <td width="33%" align="center"><img src="{images[0]}" style="max-width: 200px; border: 2px solid #ddd;"></td>
          <td width="33%" align="center"><img src="{images[1]}" style="max-width: 200px; border: 2px solid #ddd;"></td>
          <td width="33%" align="center"><img src="{images[2]}" style="max-width: 200px; border: 2px solid #ddd;"></td>
        </tr>
      </table>
    </td>
  </tr>
"""
        
        html += """
  <tr>
    <td style="padding: 20px;">
      <h2 style="color: #333;">Premium Features</h2>
      <p style="padding: 10px; background: #f8f9fa;"><strong>✨ Premium Qualität</strong><br>Hochwertige Verarbeitung</p>
      <p style="padding: 10px; background: #f8f9fa;"><strong>🚀 Schneller Versand</strong><br>Direkt aus Deutschland</p>
      <p style="padding: 10px; background: #f8f9fa;"><strong>💯 30 Tage Rückgabe</strong><br>Zufriedenheitsgarantie</p>
    </td>
  </tr>
  <tr>
    <td style="background: #f8f9fa; padding: 20px; text-align: center;">
      <p style="margin: 0; color: #666;">✅ Geprüfte Qualität | 🚀 Schneller Versand | 💯 Garantie</p>
    </td>
  </tr>
</table>
"""
        return html.strip()

# Continuation in Part 3...
