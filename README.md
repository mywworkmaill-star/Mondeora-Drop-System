# Mondeora — eBay / AliExpress otomasyonu

## Durum
Canlı kullanıma hazır olduğu **varsayılmaz**. Güncel durum ve engeller `data/readiness_report.json` dosyasındadır. Varsayılan çalışma güvenli izlemedir; gerçek ilan, fiyat/stok değişikliği ve tedarikçi siparişi kapalıdır. API tokenı almak, ürün/sipariş yetkisinin veya teslimatın kanıtı değildir.

## Başlatma (Python 3.11)
`START_SYSTEM.bat` veya:
```bat
"C:\Program Files\Python311\python.exe" main.py --mode full
```
Panel: http://127.0.0.1:5000 — yalnızca bu makineden erişilir. Kapatma: Ctrl+C. İkinci sistem örneği dosya kilidiyle engellenir. Bilgisayar yeniden başlatıldığında otomatik başlama bu sürümde kurulmamıştır.

```bat
"C:\Program Files\Python311\python.exe" main.py --check
"C:\Program Files\Python311\python.exe" main.py --live-check
"C:\Program Files\Python311\python.exe" main.py --mode full --smoke-seconds 5
```
`--live-check` yalnızca okuma çağrıları yapar. Canlı hazırlık engeli varsa çıkış kodu 2 normaldir; raporu inceleyin. Canlı yazma açıkken ön kontroller başarısızsa başlatma engellenir.

## Canlı kullanım ön koşulları
- Gerçek toptan tedarikçi anlaşması ve eBay dropshipping politikası uygunluğu. Başka bir perakendeci/pazaryerinden satış sonrası satın alım, eBay politikasına uygun kabul edilmez.
- Almanya mağazasına ait gerçek ödeme/iade/kargo politika kimlikleri ve etkin depo/konum anahtarı.
- Tedarikçi tarafından onaylı gerçek ürün/SKU eşleştirmesi, eBay kategori ve zorunlu ürün nitelikleri, Almanya teslimat maliyeti ve gerçek stok.
- Satıcı/kategoriye ait gerçek komisyon, sabit ücret ve vergi rezervi. `EBAY_FEE_PERCENT` zorunludur; kargo ücretsiz varsayılmaz. Varsayılan minimum net kâr hedefi 25 EUR ve minimum marj yüzde 25'tir. Vergi/muhasebe uygunluğu ayrıca doğrulanmalıdır.
- Ürün güvenliği, CE/GPSR, Almanya ambalaj/EPR ve tüketici hakları yükümlülükleri satıcı tarafından doğrulanmalıdır.
- Onaylı kontrollü gerçek siparişle ödeme, tedarikçi teslimatı ve takip doğrulanmadan uçtan uca tamamlandı denmez.

Güvenlik anahtarları `.env` içinde açıkça onaylanmadıkça kapalıdır:
```dotenv
AUTOMATION_LIVE_WRITES=false
SUPPLIER_AGREEMENT_CONFIRMED=false
ALLOW_ORDER_PURCHASES=false
LIVE_ACCEPTANCE_CONFIRMED=false
MIN_PROFIT_EUR=25
```
Bu anahtarları yalnızca gerçek kontrollerden sonra değiştirin; raporu yeşile çevirmek için sahte onay girmeyin. `LIVE_ACCEPTANCE_CONFIRMED` bir kullanıcı beyanıdır, otomatik test sonucu değildir.

## Veri güvenliği
`.env`, veritabanı ve yedekler gizlidir. Tokenlar loglanmaz; panel eski ham logları sunmaz. API hataları başarı gibi işlenmez. Stok satış adedinden türetilmez. Sipariş satırı dış çağrıdan önce kaydedilir; sonucu belirsiz satın alımlar `manual_review` durumunda otomatik tekrarlanmaz. Yeniden denemeden önce tedarikçi hesabından uzlaştırma gerekir.

## Ek salt-okunur AliExpress yetenekleri

Mevcut `AliExpressAPIClient` üzerinden, ayrı bir `iop` paketi olmadan:

```python
from src.api.aliexpress_client import AliExpressAPIClient
client = AliExpressAPIClient()
category_envelope = client.get_category_tree(lang='en_US')
# Gerçek görselin saf Base64 içeriği; data-URL öneki kullanmayın.
image_envelope = client.search_products_by_image(image_base64)
```

Görsel arama V2 Almanya/EUR/de parametreleriyle çalışır. Bu yöntemler kontrol edilmiş ham API zarfını döndürür; `result` JSON metni olabilir. Sonuçlar doğrulanmış stok, kargo, ürün güvenliği, kâr veya eBay kategori eşleşmesi değildir. Görsel sonuçları henüz otomatik araştırma döngüsüne bağlanmamıştır; programatik çağrı olarak kullanılabilir. Canlı okuma kanıtı `data/discovery_api_verification.json`, son regresyon sonucu `data/discovery_extension_tests.json` dosyasındadır. Token veya ham yanıt gövdelerini loglamayın.

## Afterpay istek hazırlığı — canlı ödeme değil

`client.prepare_order_afterpay(order_id)` kullanıcının verdiği `aliexpress.ds.order.afterpay` / `req={"order_id":"..."}` sözleşmesini yerel olarak hazırlar. Sipariş kimliği pozitif ASCII rakamlardan oluşan tam bir metin olmalıdır; örnek `order id` reddedilir. Ağ çağrısı yapmaz, ödeme gerçekleştirmez, zamanlayıcıya bağlı değildir. Dönen `submitted`, `payment_verified` ve `live_execution_supported` alanları `False` olur. Resmi işlem/yanıt sözleşmesi, siparişe özel ödeme izni, kesin toplam ve kalıcı mükerrer ödeme/uzlaştırma kontrolleri doğrulanmadan hazırlanmış istek gönderilmemelidir. Bu katman otomatik ödemenin tamamlandığı anlamına gelmez.

## DS sipariş oluşturma adaptörü

`client.create_ds_order(product_id, quantity, buyer_email, shipping_address, sku_id=..., external_order_id=...)` resmi `aliexpress.ds.order.create` yöntemini kullanır. Önceki `create_order` yöntemi değiştirilmeden korunur; otomatik sipariş akışı yeni adaptöre geçirilmemiştir. Ortak güvenlik kontrolleri gerçek stok/SKU/EUR fiyatını, Almanya adresini, doğrulanmış kargo maliyetini ve canlı yazma/satın alma izinlerini gerektirir. Salt-okunur işlem kilidi doğrudan istemci çağrılarını da engeller.

Yeni adaptör `out_order_id` alanına tam sipariş-satır ilişki kimliğini taşır; bu alan sağlayıcı tarafında idempotency garantisi olarak kabul edilmez. `ds_extend_request.payment` her zaman `try_to_pay="false"`, `pay_currency="EUR"` içerir. Örnek adres, ürün, promosyon ve vergi/pasaport bilgileri üretime kopyalanmaz. Çağıran akış, gerçek çağrı öncesinde sipariş satırını kalıcı rezerve etmeli ve gerekli kapsamlı onayı doğrulamalıdır. Belirsiz cevap veya taşıma hatası otomatik tekrar edilmez; uzlaştırma gerekir. Adaptör sahte HTTP yanıtlarıyla test edilmiştir; gerçek tedarikçi siparişi/ödeme oluşturulmamıştır. Kesin kargo/checkout kanıtı yoksa mevcut üretim yolu siparişi engellemeye devam eder.

Resmi kaynak: https://openservice.aliexpress.com/doc/api.htm?cid=20900#/api?cid=21038&path=aliexpress.ds.order.create&methodType=GET/POST

## Kategori sorgusu

`client.get_categories(category_id='15', language='en', app_signature=None)` `aliexpress.ds.category.get` yöntemini çağırır; varsayılan dil `de` olur. `category_id` isteğe bağlıdır; verildiğinde tam pozitif ASCII rakam metni olmalıdır. `app_signature` isteğe bağlı uygulama parametresidir, otomatik TOP `sign` alanıyla aynı şey değildir; örnek `your signature` gönderilmez. Mevcut imzalı ve yetkilendirilmiş TOP taşıması kullanılır. Yanıttaki `resp_result.resp_code` kontrol edilir, `categories.category` sarmalayıcısı listeye dönüştürülür; hatalı yanıt boş başarıya çevrilmez. Bu AliExpress kategorisidir, eBay kategori eşleştirmesi değildir. Canlı salt-okunur kanıt: `data/category_api_verification.json`.

## Üyelik avantajları ve DS takip sorgusu

- `client.get_member_benefits()` parametresiz `aliexpress.ds.member.benefit.get` çağrısını yapar. Doğrudan sonuç listesi ve canlıda gözlenen `result.benefit_catalog` sarmalayıcısı desteklenir; başlık isteğe bağlıdır. `canApply` ve `canBenefit` gerçek booleanlara dönüştürülür. Avantaj `code` alanı (örneğin `auto-pay`) işlem hata kodu değildir. Uygunluk bilgisi canlı yazma/satın alma/ödeme izni sağlamaz ve bu izinleri değiştirmez.
- `client.get_order_tracking(order_id, language='en_US')` `aliexpress.ds.order.tracking.get` yöntemine tam `ae_order_id` gönderir. Başarı `ret` alanı ve `data.tracking_detail_line_list` yapısı kontrol edilir. Bu yeni sorgu otomatik eBay takip yüklemesine bağlanmamıştır; mevcut sipariş/ürün/adet/taşıyıcı eşleştirme ve uzlaştırma kontrollerinin yerini almaz. Örnekteki `12345` kullanıcı siparişi sayılıp üretimde sorgulanmaz. Gerçek siparişle canlı takip doğrulaması ayrıca gereklidir.

## Kullanılmayan fotoğrafı silme — varsayılan önizleme

`client.delete_unused_photo(image_repository_id)` yalnızca istek önizlemesi döndürür, ağ çağrısı yapmaz. `aliexpress.photobank.redefining.delunusephoto` için gerçek gönderim ayrıca `dry_run=False`, aynı kimlikte `confirmed_image_repository_id`, etkin canlı yazma koruması, `ALLOW_PHOTOBANK_DELETIONS=true` ve tam aynı kimlikte `PHOTOBANK_DELETE_IMAGE_ID` gerektirir. Bu ayarlar entegrasyon sırasında değiştirilmemiştir; otomatik temizlik görevi eklenmemiştir. Doğrudan `_request` çağrıları da aynı izin ve hedef kapsamı kontrolünden geçer. Genel/boş hedefler ve ilave silme alanları reddedilir.

Sağlayıcı başarı cevabı yalnızca `acknowledged=True` olarak raporlanır; bağımsız geri okuma olmadığı için `deletion_verified=False` kalır. Hata kodu varsa çelişkili `is_success=true` başarı sayılmaz. Belirsiz sonuç otomatik tekrarlanmaz. Gerçek fotoğraf silinmemiştir; taşıma ve korumalar sahte HTTP ile test edilmiştir.

Resmi belge: https://openservice.aliexpress.com/doc/api.htm?cid=20900#/api?cid=20894&path=aliexpress.photobank.redefining.delunusephoto&methodType=GET/POST

## Fotoğraf bankasına görsel yükleme

`client.upload_image(image_path, group_id='0', file_name=None, dry_run=True)` gerçek PNG/JPEG dosyasını `rb` modunda, en fazla 3.000.001 bayt okuyarak denetler; 3.000.000 bayttan büyük dosyalar reddedilir. Pillow ile görsel bütünlüğü, en fazla 5000×5000 boyut, uzantı ve MIME uyumu kontrol edilir. Dosya adı en fazla 256 karakterlik yalın ad olmalıdır. `/Users/IopSdk.py` gibi kaynak kod dosyaları ve bozuk görseller reddedilir. İlk sürümde PNG/JPEG desteklenir.

Varsayılan yalnızca önizlemedir; görsel içeriği/tokenlar loglanmaz. Gerçek gönderim için `dry_run=False`, önizlemedeki tam `confirmed_sha256`, açık canlı yazma koruması, `ALLOW_PHOTOBANK_UPLOADS=true` ve aynı içerik özetinde `PHOTOBANK_UPLOAD_SHA256` gerekir. Bu ayarlar entegrasyonda değiştirilmemiştir. İzinler doğrudan `_request` içinde de denetlenir. İstek `image_bytes` dosyasını multipart olarak, metin alanlarını imzalayarak gönderir; dosya baytları metin imzasına konmaz.

Başarı cevabı yalnızca acknowledgement verir; bağımsız geri okuma olmadan `upload_verified=False` kalır. Belirsiz sonuç tekrar gönderilmez. Gerçek dosya yüklenmemiştir; taşıma, dosya kontrolleri ve izinler izole HTTP testleriyle doğrulanmıştır. Pillow mevcut Python 3.11 ortamında kuruludur.

Resmi belge: https://openservice.aliexpress.com/doc/api.htm?cid=20900#/api?cid=20894&path=aliexpress.photobank.redefining.uploadimageforsdk&methodType=GET/POST

## Fotoğraf bankasını sayfalı listeleme

`client.list_photobank_images(group_id='0', current_page=1, page_size=20, location_type='0')` `aliexpress.photobank.redefining.listimagepagination` üzerinden yalnızca tek sayfa okur. İstek `aeop_image_pagination_request` JSON alanında gönderilir. Sıfır sayfa/boyut ve örnek yer tutucular kullanılmaz; sayfa pozitif tamsayı, sayfa boyutu yerel güvenlik sınırı olarak 1..50, grup kimliği tam rakam metni olmalıdır. İlk sürümde yalnız belgelenmiş `location_type='0'` desteklenir.

Yanıtta başarı, kayıt kimlikleri, toplamlar ve varsa sorgu eşleşmesi kontrol edilir. Dönen toplam ile o sayfadaki kayıt sayısı ayrı tutulur; `all_pages_fetched` tek sayfadan bütün deponun okunduğunu varsaymaz. Bu yöntem görsel silmez/yüklemez ve sıfır referans sayısını otomatik silme izni saymaz. Gerçek salt-okunur API denemesi `InsufficientPermission` döndürdü; uygulama yetkisi olmadan canlı listeleme doğrulanmış değildir. Yerel testler sahte HTTP yanıtları kullanır.

Resmi belge: https://openservice.aliexpress.com/doc/api.htm?cid=20900#/api?cid=20894&path=aliexpress.photobank.redefining.listimagepagination&methodType=GET/POST

## Geçici görsel yükleme

`client.upload_temp_image(image_path, src_file_name=None, dry_run=True)` `aliexpress.image.redefining.uploadtempimageforsdk` için ayrı adaptördür; multipart alanı `file_data`, metin alanı `src_file_name` olur. Fotoğraf bankasının grup/dosya alanları bu yönteme gönderilmez. Resmi parametre metnindeki JPG/JPEG/GIF biçimleri desteklenir; PNG ve Python kaynak dosyaları reddedilir. Belgenin genel açıklamasında PDF geçmesine rağmen parametrelerde net bir PDF sözleşmesi bulunmadığından bu sürüm PDF yüklemez. Boyut/bayt sınırları 5000×5000 ve 3.000.000 bayt olarak yerel muhafazakâr korumadır; bu endpoint için belgelenmiş sağlayıcı limiti olduğu iddia edilmez.

Pillow verify() sonrasında gerçek piksel decode da yapılır; yalnız başlık doğrulamasından geçen kesik JPEG/GIF dosyaları kabul edilmez. Gerçek gönderim için açık canlı yazma, ayrı `ALLOW_TEMP_IMAGE_UPLOADS=true`, aynı içerik özetinde `TEMP_IMAGE_UPLOAD_SHA256` ve `confirmed_sha256` gerekir; fotoğraf bankası yükleme izni bunu açmaz. Varsayılan önizleme ağ çağrısı yapmaz. Geri dönen URL yalnız acknowledgement olup `upload_verified=False` kalır; dosyanın uzaktaki kalıcılığı/süresi ayrıca doğrulanmalıdır. Gerçek yükleme yapılmamış, multipart ve korumalar sahte HTTP ile test edilmiştir.

Resmi belge: https://openservice.aliexpress.com/doc/api.htm?cid=20900#/api?cid=20894&path=aliexpress.image.redefining.uploadtempimageforsdk&methodType=GET/POST

## Bakım
Yeni çalışan sistem `main.py`, `src/launcher.py`, `src/runtime.py`, `src/readiness.py`, `src/api/`, `src/automation/engine.py`, `src/database/models.py` ve `src/dashboard.py` üzerinden çalışır. Kök klasördeki tarihî token/kurulum araçları yeni çalışma yolunun parçası değildir; eski XML yenileme araçlarını çalıştırmayın. Güncel kontrollere `main.py --live-check` ile erişin.

Regresyon kontrolleri kullanıcının isteği gereği proje dışındaki doğrulama klasöründe tutulur. Yerel testler, gerçek API yetkileri veya gerçek satın alma kanıtı olarak sunulmaz.

