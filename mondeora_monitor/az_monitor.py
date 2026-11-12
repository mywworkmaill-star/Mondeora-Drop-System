"""Detailed read-only A-Z monitor; no engine imports or commerce mutations.

Run: python -m mondeora_monitor.az_monitor --port 8768
Only explicit reports and sanitized loopback health are inputs. No raw logs,
credentials, buyer data, delegate transcripts or arbitrary files are served.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from . import automation_monitor as core

# Each tuple is a finite observable acceptance substep, NOT an effort weight.
# An absent live proof remains unknown even when the enclosing suite is current.
STAGES = (
 ('access', '01 · Kaynak erişimi ve hesaplar', (
  ('runtime','Python 3.11 ve kaynak sözdizimi','Ben','runtime','software'),
  ('suite','Güncel kaynakla tam regresyon','Ben','suite','software'),
  ('ebay','eBay envanter / sipariş gerçek okuması','Erişim / Ben','ebay_read','live'),
  ('supplier','AliExpress seçili SKU gerçek okuması','Erişim / Ben','supplier_read','live'),
  ('commercial','eBay ticari hesap statüsü','Sen','commercial','live'),
  ('tax','İşletme ve vergi uygulaması','Sen','tax','live'))),
 ('research', '02 · Niş araştırması ve aday keşfi', (
  ('office','Büro nişi araştırması','Ben',None,'unknown'),
  ('home','Ev nişi araştırması','Ben',None,'unknown'),
  ('garden','Bahçe nişi araştırması','Ben',None,'unknown'),
  ('dedup','Aday tekilleştirme / kaynak provenansı','Ben',None,'unknown'),
  ('drafts','Gerçek araştırmadan hazırlanmış taslaklar','Ben','sourcing','artifact'),
  ('refresh','Seçili ürün fiyat / stok tazeleme','Ben',None,'unknown'))),
 ('sku', '03 · Kesin ürün / SKU / adet', (
  ('identity','Ürün ve seçili varyant kimliği','Ben',None,'unknown'),
  ('quantity','Paket içeriği ve adet eşleşmesi','Ben',None,'unknown'),
  ('stock','Varyant düzeyinde güncel stok','Ben',None,'unknown'),
  ('price','Seçili SKU EUR kaynak fiyatı','Ben',None,'unknown'),
  ('destination','Almanya / posta kodu kapsamı','Ben',None,'unknown'),
  ('image_ref','SKU görsel referans eşleşmesi','Ben','images','artifact'))),
 ('market', '04 · Pazar / talep / kâr', (
  ('exact','Kesin ürün pazar karşılaştırması','Ben',None,'unknown'),
  ('related','İlgili ilan fiyatı; satış kanıtı değildir','Ben',None,'unknown'),
  ('demand','Platform / dönem / gerçek satış metriği','Ben',None,'unknown'),
  ('profit','25 € net kâr ve %25 marj koşulu','Ben','product_profit','live'),
  ('reject','Ticari eleme ve nedenleri','Ben',None,'unknown'))),
 ('finance', '05 · Ücret / checkout / rezerv', (
  ('category','Kategori bazlı gerçek ücret politikası','Ben','fees','live'),
  ('checkout','Kesin SKU / adet / konum checkout toplamı','Erişim / Ben','checkout','live'),
  ('freight','Nihai kargo / vergi / ithalat maliyetleri','Ben',None,'unknown'),
  ('allocation','Çok satırlı siparişte kuruş koruyan dağıtım','Ben','order_finance','software'),
  ('reserve','Satılan birim başına 2 € rezerv','Ben','order_finance','software'),
  ('ledger','Gerçek ödeme kanıtlı finans kaydı','Ben',None,'unknown'))),
 ('compliance', '06 · Üretici / güvenlik / kullanım hakkı', (
  ('manufacturer','Hukuki üretici kimliği','Tedarikçi / Ben','safety','live'),
  ('eu','Uygulanabilir AB sorumlu kişi bilgisi','Tedarikçi / Ben','safety','live'),
  ('safety','Ürüne özgü güvenlik / uyarılar / belgeler','Tedarikçi / Ben','safety','live'),
  ('rights','Ticari fotoğraf ve türev kullanım izni','Tedarikçi / Ben','rights','live'),
  ('review','Belgelerin gerçek ürün / SKU ile eşleşmesi','Ben',None,'unknown'))),
 ('supplier', '07 · Tedarikçi / depo / iade koşulları', (
  ('agreement','Doğrudan gönderim anlaşması','Tedarikçi / Ben','supplier_terms','live'),
  ('dispatch','Gerçek gönderim deposu','Tedarikçi / Ben','warehouse','live'),
  ('location','eBay konumunun gerçek depoyla eşleşmesi','Ben','warehouse','live'),
  ('shipping','Gönderim hizmeti ve teslim taahhüdü','Tedarikçi / Ben',None,'unknown'),
  ('returns','Tedarikçi iade / geri ödeme şartları','Tedarikçi / Ben',None,'unknown'))),
 ('listing', '08 · İlan / görseller / yayın', (
  ('copy','Almanca başlık / açıklama / ürün özellikleri','Ben',None,'unknown'),
  ('taxonomy','Kategori ve zorunlu özellikler','Ben',None,'unknown'),
  ('png','Kesin SKU için 1600×1600 PNG seti','Ben','images','artifact'),
  ('hosting','Gerçek eBay görsel yükleme ve geri okuma','Ben / Canlı kabul','hosting','live'),
  ('policies','Gerçek hesap politika kimlikleri','Ben',None,'unknown'),
  ('publication','İlan yayınlama ve bağımsız geri okuma','Ben / Canlı kabul',None,'unknown'))),
 ('purchase', '09 · Ödenmiş satış / alım / ödeme', (
  ('paid','Ödenmiş / iptalsiz eBay sipariş okuması','Ben',None,'unknown'),
  ('mapping','Satış satırı → kesin tedarikçi SKU eşleşmesi','Ben',None,'unknown'),
  ('preflight','Tüm satırlar için maliyet / izin ön kontrolü','Ben',None,'unknown'),
  ('supervised','İlk alım için kapsamlı süreli gözetim izni','Sen / Ben',None,'unknown'),
  ('reservation','Kalıcı rezervasyon ve tekrar satın almama','Ben',None,'unknown'),
  ('create','Gerçek tedarikçi sipariş oluşturma / geri okuma','Ben / Canlı kabul',None,'unknown'),
  ('payment','Yetkili ödeme ve gerçek paid-time kanıtı','Sen / Canlı kabul','payment','live'))),
 ('tracking', '10 · Posta / sevkiyat / takip', (
  ('mailbox','Yetkili gerçek posta hesabına salt-okunur erişim','Erişim / Ben','email','live'),
  ('auth','Mesaj hashine bağlı bağımsız kaynak doğrulama','Ben',None,'unknown'),
  ('shipment','Gerçek tedarikçi sevkiyatını doğrulama','Ben',None,'unknown'),
  ('carrier','Taşıyıcı / paket / ürün / adet eşleşmesi','Ben',None,'unknown'),
  ('upload','eBay takip yükleme ve bağımsız geri okuma','Ben / Canlı kabul','tracking','live'),
  ('reconcile','Belirsiz sonucu tekrar göndermeden uzlaştırma','Ben',None,'unknown'))),
 ('returns', '11 · Teslimat ve manuel iadeler', (
  ('delivery','Gerçek teslimat durumu','Ben',None,'unknown'),
  ('intake','İlk dönemde manuel iade talebi','Sen / Ben',None,'unknown'),
  ('address','Satıcı / iade / gönderim adreslerinin ayrımı','Ben',None,'unknown'),
  ('refund','Manuel iade ve gerçek geri ödeme uzlaştırma','Sen / Ben',None,'unknown'),
  ('close','Gerçekleşen maliyet ve sipariş kapanışı','Ben',None,'unknown'))),
 ('recovery', '12 · Kurtarma / başlangıç / yedekler', (
  ('readonly','Yetkisiz komut / canlı yazma korumaları','Ben','readonly','software'),
  ('restart','Tek süreç / kapanış / çökme sonrası başlatma','Ben','restart','software'),
  ('backup','Gerçek DB yedeği / hash / izole geri yükleme','Ben','backup','software'),
  ('heartbeat','Gerçek zamanlayıcı heartbeat / yerel uyarı','Ben','heartbeat','software'),
  ('registration','Kalıcı Windows başlangıç kaydı','Sen / Onay','startup','live'),
  ('reboot','Onaylı gerçek reboot sonrası doğrulama','Sen / Onay','startup','live'))),
)


def snapshot(project=core.PROJECT):
    """Build a finite lifecycle view, retaining the original fixed denominator."""
    base = core.snapshot(project)
    rows = {row['id']: row for row in base['criteria']}
    stages = []
    for stage_id, title, specs in STAGES:
        steps = []
        for key, name, owner, criterion, kind in specs:
            accepted = bool(criterion and rows[criterion]['verified'])
            software = 'tested' if kind == 'software' and accepted else 'unknown'
            live = 'verified' if kind == 'live' and accepted else ('blocked' if kind == 'live' else 'unknown')
            evidence = ('Güncel sürümde yazılım / yerel süreç kontrolü geçti; canlı ticaret kanıtı değildir.' if software == 'tested'
                        else 'Üst kabul kontrolünde canlı kanıt bildirildi; kanıt kapsamı bu alt adımla sınırlıdır.' if live == 'verified'
                        else 'Yerel çıktı kontrolü geçti; canlı erişim, hak veya yayın kanıtı değildir.' if kind == 'artifact' and accepted
                        else 'Bu alt adım için yeterli doğrulanmış kanıt yok; dosyanın varlığı başarı sayılmaz.')
            steps.append(dict(id=stage_id + '.' + key, title=name, owner=owner, criterion=criterion,
                              software=software, live=live, artifact_checked=kind == 'artifact' and accepted, evidence=evidence))
        stages.append(dict(id=stage_id, title=title, steps=steps))
    steps = [s for stage in stages for s in stage['steps']]
    return dict(checked_at=base['checked_at'], source_fingerprint=base['source_fingerprint'],
                acceptance={k: base[k] for k in ('verified', 'total', 'percent', 'all_complete', 'tests_current', 'deployment_current')},
                criteria=[{k: r[k] for k in ('id', 'title', 'verified', 'owner', 'group')} for r in base['criteria']],
                tests=base['tests'], runtime=base['runtime'], research=base['research'], stages=stages,
                substeps={'total': len(steps), 'software_tested': sum(s['software'] == 'tested' for s in steps),
                          'live_verified': sum(s['live'] == 'verified' for s in steps),
                          'blocked': sum(s['live'] == 'blocked' for s in steps)}, events=[],
                scope='25 sabit kabul kontrolü ayrı; alt adımlar iş gücü yüzdesi değildir. Yalnız gözlemlenen rapor / sağlık değişiklikleri izlenir; tüm asistan işlemleri izlenmez.')
