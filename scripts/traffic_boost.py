"""
Traffic Boost — Mondeora sürekli reklam/trafik optimizasyonu.

"Patlama olana kadar sürekli oyna" talebi için: her çalıştırmada
1) Reklamsız (hiçbir kampanyada olmayan) aktif listing'leri bulur, BASIS
   kampanyasına %20 bid ile ekler.
2) Zaten reklamda olup son 7 günde düşük performans gösteren (0-1 görüntülenme)
   listing'lerin bid'ini kademeli artırır (20% -> 25% -> 30%, üst sınır 35%).
3) İyi performans gösterenleri (>=5 görüntülenme) olduğu gibi bırakır
   (zaten çalışıyor, bütçeyi oraya yığmaya gerek yok).

Cron'dan günde 1-2 kez çalıştırılır (kampanyalar statik kalmasın, "hep
uygula" talebine göre sürekli yeniden ayarlanır). Gerçek satış/trafik
patlaması olana kadar bid kademeli yükselir; 35% tavanına ulaşınca durur
(agresiflik ile kâr marjı dengesini bozmamak için).

Usage: python scripts/traffic_boost.py
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from src.velocity_guard import pace  # throttle bulk writes - see src/velocity_guard.py

BASIS_CAMPAIGN_ID = '169024806017'
# 2026-11-21 (user-directed "trafik patlamasi" push): raised from 20/35 to
# 60/65 after confirming live that eBay's real bidPercentage ceiling is at
# least 100% (our old 35 cap was self-imposed, not an eBay limit) and that
# COST_PER_SALE means zero cost unless an item actually sells. At ~3x markup,
# breakeven is ~67% bid -- MAX_BID stays a few points under that so automated
# escalation on weak-view listings never crosses into a guaranteed per-sale
# loss on its own; going above 65% (up to the real ~100% ceiling) is a
# deliberate, explicit user decision, not something this script does alone.
DEFAULT_BID = 60.0
BID_STEP = 5.0
MAX_BID = 65.0
LOW_VIEW_THRESHOLD = 2  # views in last 7 days considered "weak"


def main():
    from api.ebay_client import eBayAPIClient
    import sqlite3
    ebay = eBayAPIClient()

    # 1) Collect ALL ads across ALL running/scheduled campaigns (listingId -> (campaign_id, ad_id, bid))
    all_ads = {}
    camp_resp = ebay._request('GET', '/sell/marketing/v1/ad_campaign?campaign_status=RUNNING,SCHEDULED&limit=200')
    for camp in camp_resp.get('campaigns', []):
        cid = camp['campaignId']
        try:
            ar = ebay._request('GET', f'/sell/marketing/v1/ad_campaign/{cid}/ad?limit=200')
        except Exception:
            continue
        for ad in ar.get('ads', []):
            lid = ad.get('listingId')
            if lid:
                all_ads[lid] = {
                    'campaign_id': cid,
                    'ad_id': ad['adId'],
                    'bid': float(ad.get('bidPercentage') or 0),
                }

    # 2) All our active listings
    conn = sqlite3.connect('data/dropshipping.db')
    c = conn.cursor()
    c.execute("SELECT id, ebay_item_id FROM products WHERE is_listed=1 AND ebay_item_id IS NOT NULL")
    listings = [(pid, lid) for pid, lid in c.fetchall() if lid]
    conn.close()

    # 3) Traffic report for the last 7 days (views per listing)
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
    views_by_listing = {}
    try:
        tr = ebay._request('GET', '/sell/analytics/v1/traffic_report', params={
            'dimension': 'LISTING',
            'filter': f'marketplace_ids:{{EBAY_DE}},date_range:[{start}..{end}]',
            'metric': 'LISTING_VIEWS_TOTAL',
            'limit': 200,
        })
        for rec in tr.get('records', []):
            lid = rec['dimensionValues'][0]['value']
            views_by_listing[lid] = int(rec['metricValues'][0]['value'])
    except Exception:
        pass

    added, bumped, skipped = [], [], 0

    for pid, listing_id in listings:
        ad = all_ads.get(listing_id)
        if not ad:
            # Not promoted at all -> add to BASIS at default bid
            try:
                pace('ad_bid_update')  # velocity guard - see src/velocity_guard.py
                ebay._request('POST', f'/sell/marketing/v1/ad_campaign/{BASIS_CAMPAIGN_ID}/ad', json={
                    'listingId': listing_id, 'bidPercentage': str(DEFAULT_BID)
                })
                added.append((pid, listing_id))
            except Exception:
                pass
            continue

        views = views_by_listing.get(listing_id, 0)
        if views <= LOW_VIEW_THRESHOLD and ad['bid'] < MAX_BID:
            new_bid = min(ad['bid'] + BID_STEP, MAX_BID)
            try:
                pace('ad_bid_update')  # velocity guard - see src/velocity_guard.py
                ebay._request(
                    'POST',
                    f"/sell/marketing/v1/ad_campaign/{ad['campaign_id']}/ad/{ad['ad_id']}/update_bid",
                    json={'bidPercentage': str(new_bid)}
                )
                bumped.append((pid, listing_id, ad['bid'], new_bid))
            except Exception:
                pass
        else:
            skipped += 1

    if not (added or bumped):
        return  # nothing changed -> stay quiet (alert-only convention)

    lines = [f"Traffic Boost — {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    lines.append(f"Yeni reklama eklenen: {len(added)} | Bid yükseltilen: {len(bumped)} | Değişmeyen: {skipped}")
    for pid, lid in added:
        lines.append(f"  ➕ ID {pid} (listing {lid}) -> BASIS %{DEFAULT_BID:.0f}")
    for pid, lid, old, new in bumped:
        lines.append(f"  ⬆️  ID {pid} (listing {lid}): %{old:.0f} -> %{new:.0f} (düşük görüntülenme)")

    print('\n'.join(lines))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Traffic boost crashed: {e}")
        sys.exit(1)
    sys.exit(0)
