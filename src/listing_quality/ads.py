"""eBay Promoted Listings bid automation: new listings get a visibility BOOST bid for a fixed
window, then automatically decay to the cheaper steady-state bid. Grounded in real campaign data
read this session: MONDEORA-BASIS-01 had all 15 live listings stuck at 2.0% while sibling
campaigns (Auto Pet Listings, iPhone Case Campaign) already ran the same listings' category at
5.0%, and our own ebay-promoted-listings skill already documented '5% first 2 weeks then 2%' as
the intended strategy - this module is the first time that strategy is actually code, not just a doc.

Never invents a bid number: BOOST_BID/STEADY_BID are config, not guesses, and decay only ever
fires on a listing this module itself boosted (boosted_at recorded at boost time).
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = str(ROOT / 'data' / 'dropshipping.db')

BOOST_BID = '5.0'      # new-listing visibility window
STEADY_BID = '2.0'     # cost-saving bid once the listing has had its visibility window
BOOST_DAYS = 14


def _db(db_path=None):
    db = sqlite3.connect(db_path or DB_PATH)
    db.execute('create table if not exists ad_bid_boosts ('
               'listing_id text primary key, ad_id text, campaign_id text, '
               'boosted_at text not null, decayed_at text)')
    return db


def record_boost(ad_id, listing_id, campaign_id, db_path=None):
    """Call right after an ad is created at BOOST_BID so decay_due_boosts() can find it later."""
    if not ad_id or not listing_id:
        return
    db = _db(db_path)
    try:
        db.execute('insert or ignore into ad_bid_boosts (listing_id, ad_id, campaign_id, boosted_at) values (?,?,?,?)',
                   (str(listing_id), str(ad_id), str(campaign_id), datetime.now(timezone.utc).isoformat()))
        db.commit()
    finally:
        db.close()


def decay_due_boosts(api, days=BOOST_DAYS, new_bid=STEADY_BID, db_path=None):
    """Step any boost older than `days` down to `new_bid`. One bad listing must not abort the batch
    (same per-item isolation rule as the rest of the pipeline)."""
    db = _db(db_path)
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = db.execute('select listing_id, ad_id, campaign_id from ad_bid_boosts '
                           'where decayed_at is null and boosted_at <= ?', (cutoff,)).fetchall()
        decayed, errors = [], []
        for listing_id, ad_id, campaign_id in rows:
            try:
                api._request('POST', f'/sell/marketing/v1/ad_campaign/{campaign_id}/ad/{ad_id}/update_bid',
                              json={'bidPercentage': str(new_bid)})
                db.execute('update ad_bid_boosts set decayed_at=? where listing_id=?',
                           (datetime.now(timezone.utc).isoformat(), listing_id))
                db.commit()
                decayed.append(listing_id)
            except Exception as ex:
                errors.append({'listing_id': listing_id, 'error': f'{type(ex).__name__}: {ex}'})
        return {'checked': len(rows), 'decayed': decayed, 'errors': errors}
    finally:
        db.close()
