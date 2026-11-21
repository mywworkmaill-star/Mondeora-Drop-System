# Statik Kimlik Bilgisi Rotasyon Runbook'u

Bu belge, `Secrets & Credential Hygiene Engineer` (Agency) denetiminden sonra
2026-11-16'da oluşturuldu. Kapsam: .env'deki **hiç rotate edilmeyen statik
"kök" sırlar** (OAuth refresh/access token'lar HARİÇ — onlar zaten
`src/jobs.py::job_token_refresh` ile saatlik otomatik yenileniyor).

## Hangi değerler bu runbook'un kapsamında?

- `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET`
- `EBAY_APP_ID`, `EBAY_CERT_ID`, `EBAY_DEV_ID`

Bunlar OAuth zincirinin **kökü**: sızarlarsa, saatlik token-refresh job'u hiçbir
şeyi durdurmaz — saldırgan aynı app_secret ile kendi refresh akışını başlatabilir.

## Gerçek bulgu (2026-11-16)

Bu 5 değer, `.env.backup_20261108_071655` (8 gün önceki yedek, artık silindi)
ile canlı `.env` arasında **byte-byte aynıydı** — yani en az 8 gündür hiç
rotate edilmemiş. Rotasyon mekanizması yok, sadece bu runbook var.

## Ne zaman rotate edilmeli?

1. **Zamanlanmış:** 90 günde bir (takvime not düşün — bu otomasyon sistemi
   bunu kendi kendine hatırlatmıyor).
2. **Anında:** Aşağıdakilerden biri olduğunda:
   - `.env` dosyası yanlışlıkla paylaşıldıysa (ekran paylaşımı, yanlış git
     commit, yanlış kişiye dosya gönderimi).
   - Bir yedek dosyası (`.env.backup_*`) şifresiz halde bulunduysa.
   - AliExpress veya eBay hesabında şüpheli/beklenmedik API aktivitesi
     görüldüyse.

## Nasıl rotate edilir?

### AliExpress (`ALIEXPRESS_APP_KEY` / `ALIEXPRESS_APP_SECRET`)
1. https://openservice.aliexpress.com → İş Uygulaması Yönetimi → ilgili uygulama.
2. Yeni bir App Secret üret (App Key genelde sabit kalır, Secret yenilenir).
3. **ÖNCE** yeni secret'ı `.env`'e yaz, test et (`python -m src.jobs
   token_refresh --alert-only`), **SONRA** eski secret'ı konsolda iptal et.
4. `aliexpress-token-management` skill'inde HMAC-SHA256 imzalama mantığı
   secret'a bağlı — secret değişince önce test ortamında doğrulayın.

### eBay (`EBAY_APP_ID` / `EBAY_CERT_ID` / `EBAY_DEV_ID`)
1. https://developer.ebay.com/my/keys → production keyset.
2. Yeni bir keyset oluşturmak mevcut `EBAY_REFRESH_TOKEN`'ı **geçersiz kılar**
   — yeni keyset'le kullanıcı onay akışını (3-legged OAuth) yeniden
   çalıştırmak gerekir. Bu, tek seferlik, insan-onaylı bir adımdır, otomatik
   yapılamaz.
3. Yeni keyset + yeni refresh token'ı aynı anda `.env`'e yazın.

## Kim yapar?

Hesap sahibi (Hasan) — geliştirici/otomasyon bu adımı başlatamaz çünkü her
ikisi de tarayıcı tabanlı, insan-onaylı bir konsol girişi gerektiriyor.
Otomasyon sadece **hatırlatma** ve **test doğrulaması** sağlayabilir.
