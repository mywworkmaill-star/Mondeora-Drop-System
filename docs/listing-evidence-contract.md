# İlan hazırlığı: kalite sözleşmesi ve belge incelemesi

## Sınırlar

Bu entegrasyon belge oluşturmaz, imzalamaz ve kendiliğinden onay vermez. Bir dosyanın SHA-256 özeti yalnız bütünlüğünü; HMAC yalnız yapılandırılmış inceleme otoritesinin onay kaydını doğrular. Bunlar belgenin hukuken doğru olduğunu tek başına kanıtlamaz. İnceleyen kişi tedarikçi ilişkisini, hakları ve ürün kapsamını gerçekte kontrol etmiş olmalıdır.

`demand_unverified`, `complete_cost_profit_unverified`, nihai kargo, global readiness ve risk onayları bağımsız kalır. Belge incelemesi bunları geçirmez. Agent gerçek üretim belgeleri veya onay anahtarları yerine test örnekleri koymamalıdır.

## Kalite alan sözleşmesi

- Başlık: `st['title']`; açıklama: `st['desc']`; kategori: `st['cat']`.
- Her varyantın özellikleri ortak `st['shared']` ile kendi `variant['aspects']` birleşimidir.
- Galeri filtrelenmiş ortak `st['imgs']` ve o varyantın görselinden oluşturulur; ham kaynak galerisi yerine gönderilecek gerçek içerik kontrol edilir.
- Yerel asgari görsel sayısı ile ideal hedef ayrıdır. Asgariyi geçen ama idealin altında kalan galeri uyarı üretir; gerçek asgari/çözünürlük eksikliği bloklanır. Eşikleri doldurmak için ürün verisi uydurulmaz.

## İncelenmiş belge kaynağı

Varsayılan manifest: `data/listing_evidence/manifest.json`.
Belgeler: aynı dizindeki `documents/` altında gerçek dosyalar.

Alternatif manifest yolu `LISTING_EVIDENCE_FILE` ile proje köküne göre göreli verilmelidir. Onay doğrulama anahtarı yalnız proje secret deposundaki `LISTING_EVIDENCE_HMAC_KEY` alanından okunur; 32 baytlık anahtarın 64 haneli hex gösterimi gerekir. Otomatik anahtar üretimi veya kurulumu yapılmaz; anahtarı/gerçek belgeyi testlere, git'e veya loglara koyma.

Manifest biçimi `version: 1` ve `records` listesidir. Her kayıt yalnız şu alanları taşır:
- `requirement`: `supplier_product_compliance`, `supplier_agreement`, `manufacturer_eu_responsible_person`, `image_rights` veya `dispatch_origin`.
- `decision`: `approved`; `reviewed_by`: gerçek yetkili inceleyici kimliği.
- `reviewed_at`, `expires_at`: saat dilimli zaman; kayıt en fazla 24 saat geçerli ve gelecekte düzenlenmemiş olmalıdır.
- `scope`: tam `product_id`, sıralı ve eksiksiz `sku_ids`, `marketplace: EBAY_DE`, `currency: EUR`, `content_sha256`.
- `documents`: her gerçek dosyanın `path` ve `sha256` kaydı. Yol `documents/` altında göreli olmalı; dışarı çıkış veya başka dosyaya bağlantı reddedilir.
- `signature`: `signature` alanı hariç kayıt JSON'unun HMAC-SHA256 özeti. Kanonik JSON: UTF-8, anahtarlar sıralı, `ensure_ascii=False`, ayraçlar virgül/iki nokta, NaN yasak.

`content_sha256`, `listing_evidence.scope_digest(product_id, st)` ile tam kaynak ve nihai içerik/varyant planına bağlanır. İnceleyici gerçek içerik ve belgeleri kontrol etmeden bunu imzalamamalıdır. Örnekteki alanları doldurmak belge doğrulaması değildir; bu yüzden üretimde örnek onay kaydı verilmez.

Eksik anahtar, bozuk imza, değişmiş belge, başka SKU/içerik, mükerrer kayıt veya süre aşımı ilgili gerekliliği bloklu bırakır. Çıktı belge içeriği veya anahtarı taşımaz. Hazırlıkta kaydedilen sonucun yayından önce ve gönderim girişinde tekrar doğrulanması zorunludur.

## Mevcut ilanda otomatik revizyon

`auto_fix` yardımcılarının çıktısı, canlı değişiklik yapılmadıysa yalnız içerik önerisidir. SKU vermek yazma izni değildir. Yazma istenirse gerçek `prepared_artifact`, güncel kural parmak izi, doğrulanmış belgeler, global readiness ve mevcut canlı yazma yetkisi gerekir. Tekli ilanda exact SKU/offer bağı kurulup fiyat/stok gibi ilgisiz alanlar korunur; Sell GET ve alıcı Browse geri-okuması başarılı olmadan doğrulandı denmez. Varyasyon revizyonu mevcut grup iş akışına bırakılır; tek SKU'ya indirgenmez.

`auto_fix_all` varsayılan olarak dry-run'dır. Marka, durum veya üretici parça numarası sırf özellik sayısını tamamlamak için eklenmez. Sağlayıcı istisnasının ham metni loglanmaz.

## Doğrulama

Python 3.11 ile tam `tests` paketi çalıştırılır. `test_prepared_quality_contract.py`, `test_listing_evidence.py`, `test_ready_document_integration.py`, `test_ready_launch.py` ve `test_auto_fix_safety.py` yanlış alan eşlemesini, eksik kanıt reddini, süre/değişiklik kontrolünü ve yazma öncesi korumaları sınar. Test fixture'ları gerçek ürün veya hukuki/mali kanıt değildir.
