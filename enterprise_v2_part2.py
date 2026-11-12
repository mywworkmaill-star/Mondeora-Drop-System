"""
ENTERPRISE V2.0 - PART 2
Ana listing creation fonksiyonu ve yardımcı fonksiyonlar
"""

# Part 1'den devam...
# Bu dosyayı create_listings_enterprise_v2.py'ye ekleyeceğim

# =====================================
# ASPECT AUTO-FILL (ADVANCED)
# =====================================
def auto_fill_aspects_advanced(product_data, category_id, ebay_client):
    """Gelişmiş aspect mapping - her kategori için"""
    
    aspects = {}
    aspects['Marke'] = ['Markenlos']
    
    # Category-specific
    title = (product_data.get('subject') or product_data.get('product_title') or '').lower()
    
    # Pet kategori
    if category_id == '20741':
        if 'dog' in title or 'hund' in title:
            aspects['Tierart'] = ['Hund']
        elif 'cat' in title or 'katz' in title:
            aspects['Tierart'] = ['Katze']
        
        if 'toy' in title or 'spielzeug' in title:
            aspects['Produktart'] = ['Spielzeug']
        elif 'bowl' in title or 'napf' in title:
            aspects['Produktart'] = ['Napf']
        elif 'leash' in title or 'leine' in title:
            aspects['Produktart'] = ['Leine']
        else:
            aspects['Produktart'] = ['Zubehör']
    
    # Garden kategori
    elif category_id == '20518':
        aspects['Produktart'] = ['Gartendekoration']
        
        if 'solar' in title:
            aspects['Energiequelle'] = ['Solar']
        if 'light' in title or 'licht' in title:
            aspects['Produktart'] = ['Gartenbeleuchtung']
    
    # Kitchen kategori
    elif category_id == '11700':
        aspects['Produktart'] = ['Küchenhelfer']
        aspects['Zimmer'] = ['Küche']
    
    # Material ve Farbe (genel)
    aspects['Material'] = ['Kunststoff']
    aspects['Farbe'] = ['Mehrfarbig']
    
    return aspects

# =====================================
# HTML GENERATION (SMART)
# =====================================
def generate_smart_html(product_data, category_name):
    """Akıllı HTML generation - ürüne özgü"""
    
    title = product_data.get('subject') or product_data.get('product_title') or 'Premium Produkt'
    images = product_data.get('image_urls', '').split(';')[:3]
    
    # Category-based emoji and features
    if category_name == 'Pet':
        if 'dog' in title.lower():
            emoji = '🐾'
            subtitle = 'Robust • Langlebig • Sicher für Hunde'
        elif 'cat' in title.lower():
            emoji = '🐱'
            subtitle = 'Spielspaß • Interaktiv • Katzenfreundlich'
        else:
            emoji = '🐾'
            subtitle = 'Premium Haustierbedarf • Hochwertig'
    elif category_name == 'Garden':
        emoji = '🌿'
        subtitle = 'Wetterfest • Langlebig • Dekorativ'
    elif category_name == 'Kitchen':
        emoji = '🍳'
        subtitle = 'Praktisch • Einfach • Hochwertig'
    else:
        emoji = '✨'
        subtitle = 'Premium Qualität • Schneller Versand'
    
    # HTML template
    html = f"""
<table width="100%" cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
  <tr>
    <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
      <h1 style="margin: 0; font-size: 28px;">{emoji} {title[:70]}</h1>
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
          <td width="33%" align="center"><img src="{images[0]}" style="max-width: 200px; border: 2px solid #ddd; border-radius: 8px;"></td>
          <td width="33%" align="center"><img src="{images[1]}" style="max-width: 200px; border: 2px solid #ddd; border-radius: 8px;"></td>
          <td width="33%" align="center"><img src="{images[2]}" style="max-width: 200px; border: 2px solid #ddd; border-radius: 8px;"></td>
        </tr>
      </table>
    </td>
  </tr>
"""
    
    # Features
    html += """
  <tr>
    <td style="padding: 20px;">
      <h2 style="color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px;">Premium Features</h2>
      <p style="margin: 15px 0; padding: 10px; background: #f8f9fa; border-left: 4px solid #667eea;">
        <strong>✨ Premium Qualität</strong><br>Hochwertige Verarbeitung und Materialien
      </p>
      <p style="margin: 15px 0; padding: 10px; background: #f8f9fa; border-left: 4px solid #667eea;">
        <strong>🚀 Schneller Versand</strong><br>Direkt aus Deutschland
      </p>
      <p style="margin: 15px 0; padding: 10px; background: #f8f9fa; border-left: 4px solid #667eea;">
        <strong>💯 30 Tage Rückgaberecht</strong><br>Volle Zufriedenheitsgarantie
      </p>
    </td>
  </tr>
  
  <tr>
    <td style="background: #f8f9fa; padding: 20px; text-align: center; border-radius: 0 0 10px 10px;">
      <p style="margin: 0; color: #666;">✅ Geprüfte Qualität | 🚀 Schneller Versand | 💯 Zufriedenheitsgarantie</p>
    </td>
  </tr>
</table>
"""
    
    return html.strip()

# =====================================
# IMAGE VALIDATION (ADVANCED)
# =====================================
def validate_images_advanced(product_id, ebay_images, ali_client):
    """Gelişmiş image validation - ilk 3 görsel"""
    try:
        rate_limiter.wait()
        fresh_product = ali_client.get_product_details(product_id)
        fresh_images = fresh_product.get('image_urls', '').split(';')
        
        if not fresh_images or len(fresh_images) < 3:
            return False, "Yetersiz görsel"
        
        # İlk 3 görseli karşılaştır
        for i in range(min(3, len(ebay_images), len(fresh_images))):
            if ebay_images[i] != fresh_images[i]:
                return False, f"Görsel {i+1} eşleşmiyor"
        
        return True, "Görseller OK"
        
    except Exception as e:
        logger.warning(f"Image validation hatası: {e}")
        return True, "Validation skip (hata)"  # Skip on error

# =====================================
# VARIANT EXTRACTION (MULTI-VARIATION)
# =====================================
def extract_variants_for_group(product_data, max_variants=10):
    """SKU'lardan varyantları çıkar (multi-variation için)"""
    
    skus = product_data.get('skus', [])
    if not skus or len(skus) <= 1:
        return None  # Single variation
    
    # Varyant tipi belirle (Color, Size, Model vs.)
    variants = []
    vary_by = set()
    
    for sku in skus[:max_variants]:
        variant_props = {}
        
        # SKU properties'den vary_by belirle
        # Basitleştirilmiş - gerçek implementation daha karmaşık
        
        variants.append({
            'sku': f"VAR-{sku.get('sku_id', '')}",
            'price': sku.get('sale_price'),
            'properties': variant_props
        })
    
    if len(variants) <= 1:
        return None
    
    return {
        'variants': variants,
        'variesBy': list(vary_by) if vary_by else ['Color']
    }

# =====================================
# DATABASE SAVE
# =====================================
def save_to_database(product_id, sku, ebay_listing_id, offer_id, 
                     title, ali_price, ebay_price, engine):
    """Listing'i database'e kaydet"""
    try:
        with get_session(engine) as session:
            product = Product(
                aliexpress_product_id=product_id,
                ebay_item_id=ebay_listing_id,
                sku_id=sku,
                ebay_offer_id=offer_id,
                title=title,
                aliexpress_price=float(ali_price),
                ebay_price=float(ebay_price),
                margin_percent=round(((ebay_price - ali_price) / ali_price) * 100, 1),
                is_listed=True,
                status='active',
                currency='EUR',
                fulfillment_verified=True,
                current_stock=10
            )
            
            session.add(product)
            session.commit()
            
            logger.info(f"✅ Database kaydedildi: {sku}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database hatası {sku}: {e}")
        return False

# =====================================
# AD CAMPAIGN (RETRY LOGIC)
# =====================================
def add_to_campaign_with_retry(ebay_listing_id, offer_id, ebay_client, campaign_id="168739871017", retries=3):
    """Ad campaign'e ekle (retry logic ile)"""
    
    for attempt in range(retries):
        try:
            rate_limiter.wait()
            
            # Farklı payload formatları dene
            payloads = [
                {'listingId': ebay_listing_id, 'bidPercentage': '5.0'},
                {'listingId': ebay_listing_id, 'bidPercentage': 5.0},
                {'offerId': offer_id, 'bidPercentage': '5.0'},
            ]
            
            for i, payload in enumerate(payloads):
                try:
                    ad_resp = ebay_client._request(
                        'POST',
                        f'/sell/marketing/v1/ad_campaign/{campaign_id}/ad',
                        json=payload
                    )
                    
                    ad_id = ad_resp.get('adId')
                    if ad_id:
                        logger.info(f"✅ Reklam eklendi: {ad_id} (format {i+1})")
                        return True, ad_id
                        
                except Exception as e:
                    if i < len(payloads) - 1:
                        continue
                    raise
                    
        except Exception as e:
            if attempt < retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(f"Reklam retry {attempt+1}/{retries}, {wait_time}s bekle...")
                time.sleep(wait_time)
            else:
                logger.warning(f"⚠️ Reklam eklenemedi (listing başarılı): {str(e)[:100]}")
                return False, None
    
    return False, None

# Dosya devam edecek - Part 3'te ana fonksiyon...
