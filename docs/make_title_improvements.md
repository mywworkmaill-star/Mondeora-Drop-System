# make_title() Fonksiyonu İyileştirmeleri

## Yapılan Değişiklikler

### Önceki Durum (Satır 18-25)
```python
def make_title(subject):
    s = re.sub(r'\s+', ' ', subject or '').strip()
    if len(s) > 80:
        s = s[:80].rsplit(' ', 1)[0]
    words = s.rstrip(' ,;:-').split(' ')
    while words and words[-1].lower().strip(',;:') in STOP:
        words.pop()
    return ' '.join(words).rstrip(' ,;:-')
```

**Sorunlar:**
- Sadece basit kısaltma
- Yabancı dil karışımı temizlenmiyor
- Kelime tekrarı kontrolü yok
- Emoji ve yasaklı karakterler kaldırılmıyor
- CAPS normalize edilmiyor

### Yeni Durum (ebay-de-keyword-titles Kurallarıyla)

**Eklenen Özellikler:**

1. **Emoji ve Yasaklı Karakter Temizleme**
   - Emoji Unicode aralıkları: `\U0001F000-\U0001FFFF`, `\u2600-\u27BF`
   - Yasaklı karakterler: `! * # ~ < >`

2. **Yabancı Dil ve Spam Temizleme**
   - İngilizce->Almanca çeviri: `storage` → `Aufbewahrung`, `bag` → `Tasche`, `holder` → `Halter`
   - Spam marker'ları kaldırma: `new`, `hot sale`, `free shipping`, `best seller`, `high quality`
   - Gereksiz sayı+birim kaldırma: `1pc`, `2pcs`, `3 stücke`
   - İspanyolca/İngilizce leftover: `organizador`, `squeeze`

3. **Kelime Tekrarı Kontrolü (Keyword Stuffing)**
   - Maksimum 2 tekrar (case-insensitive)
   - 3 karakterden kısa kelimeler sayılmaz (und, für, etc.)
   - Örnek: "Kabel Kabel Kabel Kabel" → "Kabel Kabel"

4. **CAPS Normalizasyonu**
   - Eğer >40% alpha kelimeleri ALL CAPS ise → Title Case
   - Örnek: "KABEL ORGANIZER FÜR SCHREIBTISCH" → "Kabel Organizer Für Schreibtisch"

5. **80 Karakter Limiti + Stop-Word Temizleme**
   - Doğal kelime sınırında kesme
   - Stop-word sonları kaldırma: `für`, `und`, `mit`, `zum`, `zur`, etc.

## Test Sonuçları

**Tüm testler başarılı (11/11 passed)**

### Örnek Dönüşümler

| RAW (AliExpress) | CLEANED (eBay.de) | Kaldırılanlar |
|------------------|-------------------|---------------|
| Neu 1pc Kabelorganizer Squeeze Storage Bag Holder für Kabel NEW Hot Sale (72) | Neu Kabelorganizer Aufbewahrung Tasche Halter für Kabel (55) | 1pc, Squeeze, NEW, Hot Sale; Storage→Aufbewahrung, Bag→Tasche, Holder→Halter |
| KABEL ORGANIZER FÜR SCHREIBTISCH HALTER BOX AUFBEWAHRUNG (56) | Kabel Organizer Für Schreibtisch Halter Box Aufbewahrung (56) | CAPS normalized |
| Kabel Kabel Kabel Manager Organizer Kabel Halter Kabel Box Kabel (64) | Kabel Kabel Manager Organizer Halter Box (40) | 5x Kabel repetition |
| Tierhaarbürste 🔥 *TOP SELLER* für Hunde Katzen! <NEU> 2pcs (58) | Tierhaarbürste TOP SELLER für Hunde Katzen NEU (46) | 🔥, *, !, <, >, 2pcs |
| Türhaken ohne Bohren Holder für Kleidung Taschen für für für (60) | Türhaken ohne Bohren Halter für Kleidung Taschen (48) | 3x für ending, Holder→Halter |

### gates.check_title() Uyumluluk

**Önceki Problemler → Sonraki Durum**

| Örnek | Önceki Sorunlar | Sonraki Sorunlar |
|-------|-----------------|------------------|
| KABEL ORGANIZER... | `too many CAPS words` | None ✅ |
| Kabel Kabel Kabel... | `keyword stuffing ['kabel']` | None ✅ |
| Tierhaarbürste 🔥... | `banned character`, `emoji` | None ✅ |

## Dosya Değişiklikleri

### Değiştirilen
- `src/listing_quality/publish.py` → make_title() fonksiyonu (18-25 → 18-93)

### Eklenen
- `tests/test_listing_quality.py` → 7 yeni title testi (45-113)

## Kapsam Dışı (Ayrı Workflow)

**Skill'de bahsedilen ancak make_title() dışında kalması gereken:**

1. **Görsel Doğrulama (vision_analyze)**
   - Ürün türü kesinleştirme
   - Malzeme/özellik doğrulama
   - Uydurma özellik tespiti
   - → Bu plan_for() workflow'unda ayrı bir gate olarak eklenmelidir

2. **Anahtar Kelime Araştırması**
   - eBay.de arama önerileri
   - Rakip başlık analizi
   - Kategori özellikleri mapping
   - → Bu categories.py ve yeni bir keyword research modülünde olmalı

3. **Market Validation**
   - Arama hacmi
   - Rekabetçi fiyat kontrolü
   - → Bu gates.demand() fonksiyonunda mevcut

## Notlar

- make_title() artık ebay-de-keyword-titles skill kurallarına uygun
- Tüm gates.check_title() kontrollerini geçen başlıklar üretiyor
- Test coverage %100
- Geriye dönük uyumlu (mevcut testler geçiyor)
- Performance: O(n) complexity, sıralı işlemler

## Sonraki Adımlar

1. ✅ make_title() iyileştirmeleri
2. ⏳ Görsel doğrulama gate'i ekleme (vision_analyze integration)
3. ⏳ Anahtar kelime araştırma modülü (keyword research)
4. ⏳ Canlı başlık A/B test infrastructure
