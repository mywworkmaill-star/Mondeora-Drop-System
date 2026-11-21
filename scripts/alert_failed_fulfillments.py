"""
Order fulfillment FAILURE alert — safety net.

Context (2026-11-20): 13/61 active eBay listings have no ebay_item_id
mapped in the local DB (legacy desync). If a buyer orders one of them,
auto_order_fulfillment.py safely catches the error and writes a
status='FAILED' row to order_fulfillment — but nothing previously
alerted a human. eBay's 2-day handling-time commitment means a silently
failed order risks a late-shipment flag / INR dispute / negative
feedback before anyone notices.

This script finds FAILED rows not yet alerted (alerted_at IS NULL),
prints a clear Turkish alert for each, and marks them alerted so the
same failure is never reported twice. Run on a schedule (cron); Hermes
delivers whatever this prints to the configured channel. Empty stdout
= nothing new = no notification sent (quiet tick).
"""
import sqlite3
from datetime import datetime

DB = 'C:/Users/Administrator/Desktop/Mondeora-Drop-System/data/dropshipping.db'

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""
    SELECT id, ebay_order_id, aliexpress_product_id, status, error_message, created_at
    FROM order_fulfillment
    WHERE status = 'FAILED' AND alerted_at IS NULL
    ORDER BY created_at ASC
""")
rows = c.fetchall()

if not rows:
    conn.close()
    # Nothing to report — quiet tick, prints nothing.
    raise SystemExit(0)

print("🚨 MONDEORA — SİPARİŞ EŞLEŞTİRME HATASI 🚨")
print(f"({len(rows)} sipariş otomatik işlenemedi, elle müdahale gerekiyor)")
print()
for rid, order_id, ali_id, status, err, created in rows:
    print(f"• eBay Sipariş: {order_id}")
    print(f"  Hata: {err}")
    print(f"  Oluşturulma: {created}")
    print(f"  → eBay Seller Hub'dan sipariş detayını kontrol et, AliExpress eşleşmesini elle yap.")
    print()

ids = [r[0] for r in rows]
c.executemany(
    "UPDATE order_fulfillment SET alerted_at = ? WHERE id = ?",
    [(datetime.now().isoformat(), i) for i in ids]
)
conn.commit()
conn.close()
