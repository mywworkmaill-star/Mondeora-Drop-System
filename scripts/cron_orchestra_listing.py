"""
Cron batch runner for Orchestra v5.2 (orchestra_v5_2_aliexpress_verified.py).

Replaces the broken `-m src.jobs listing_pipeline` / `new_variation_listing`
calls (src.jobs has no __main__.py -> always failed, silently masked by the
wrapper's unconditional `exit 0`). This script actually lists products.

Picks the next BATCH_SIZE ready_to_list/unlisted products (best profit first),
runs each through OrchestraV52().run() (which auto-routes to the variation
path or single-SKU path, auto-skips products with no verified dimensions,
auto-attaches the MONDEORA BASIS promoted campaign). Prints a short summary
only when something happened — quiet exit (no stdout) when there is nothing
to do, per the existing "--alert-only" convention of these cron jobs.

Usage: python scripts/cron_orchestra_listing.py [batch_size]
"""
import sys
import os
import io
import sqlite3
import contextlib
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

BATCH_SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 5


def main():
    from orchestra_v5_2_aliexpress_verified import OrchestraV52

    conn = sqlite3.connect('data/dropshipping.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT id FROM products
        WHERE is_listed = 0
          AND status = 'ready_to_list'
          AND ebay_offer_id IS NULL
          AND aliexpress_price IS NOT NULL
          AND ebay_price IS NOT NULL
        ORDER BY (ebay_price - aliexpress_price - COALESCE(shipping_cost, 0)) DESC
        LIMIT ?
    ''', (BATCH_SIZE,))
    candidate_ids = [r[0] for r in cur.fetchall()]
    conn.close()

    if not candidate_ids:
        return  # nothing to do -> stay quiet (alert-only convention)

    published, variation_published, skipped, failed = [], [], [], []
    os.makedirs('logs', exist_ok=True)
    log_path = f"logs/cron_orchestra_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    for pid in candidate_ids:
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                orchestra = OrchestraV52()
                result = orchestra.run(product_id=pid)
                orchestra.close()
        except Exception as e:
            failed.append((pid, str(e)[:120]))
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(buf.getvalue() + f"\n--- EXCEPTION for {pid}: {e}\n")
            continue

        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(buf.getvalue() + "\n")

        if not result:
            failed.append((pid, 'run() returned None'))
        elif result.get('skipped'):
            skipped.append((pid, result.get('reason')))
        elif result.get('is_variation_listing'):
            variation_published.append((pid, result.get('listing_id'), result.get('skus_created')))
        elif result.get('listing_id'):
            published.append((pid, result.get('listing_id')))
        else:
            failed.append((pid, 'unrecognized result shape'))

    if not (published or variation_published or failed):
        return  # only skips (no dimensions etc.) -> not worth alerting about

    lines = [f"Orchestra v5.2 batch — {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    lines.append(f"İşlenen: {len(candidate_ids)} | Yayınlanan: {len(published)} | "
                  f"Variation: {len(variation_published)} | Atlandı: {len(skipped)} | Hata: {len(failed)}")
    for pid, listing_id in published:
        lines.append(f"  ✅ ID {pid} → https://www.ebay.de/itm/{listing_id}")
    for pid, listing_id, n_sku in variation_published:
        lines.append(f"  ✅ ID {pid} → https://www.ebay.de/itm/{listing_id} ({n_sku} SKU)")
    for pid, err in failed:
        lines.append(f"  ❌ ID {pid}: {err}")

    print('\n'.join(lines))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Orchestra batch runner crashed: {e}")
        sys.exit(1)
    sys.exit(0)
