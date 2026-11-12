from create_listings_bulletproof_full import create_bulletproof_listings
import os

# Yeni campaign ID'yi kullan
os.environ['ACTIVE_CAMPAIGN_ID'] = '168750173017'

print('🚀 YENİ LİSTİNG + AD CAMPAIGN TEST\n')
print('='*70)

# Sadece 1 ürün oluştur
results = create_bulletproof_listings(
    keyword='cat toy',
    count=1,
    min_stock=5,
    enable_stock_check=True,
    enable_vero_check=True,
    enable_duplicate_check=True,
    enable_ad_campaign=True,  # Açık!
    parallel=False,
    strict_mode=False
)

if results['success']:
    item = results['success'][0]
    print('\n' + '='*70)
    print('✅ SONUÇ:')
    print(f'   Listing: {item["ebay_id"]}')
    print(f'   Price: €{item["price"]}')
    print(f'   Database: {item.get("db_saved")}')
    print(f'   Ad ID: {item.get("ad_id") or "Failed"}')
    
    if item.get('ad_id'):
        print('\n🎉 AD CAMPAIGN %100 ÇALIŞIYOR!')
    else:
        print('\n⚠️  Ad campaign hala başarısız')
else:
    print(f'\n⚠️  Hiç başarılı listing oluşturulamadı')
    print(f'Failed: {len(results["failed"])}')
    print(f'Skipped: {len(results["skipped"])}')
