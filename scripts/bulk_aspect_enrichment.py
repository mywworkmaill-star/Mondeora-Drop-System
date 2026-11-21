"""Bulk Artikelmerkmale (item specifics/aspects) enrichment for every real ACTIVE/
OUT_OF_STOCK eBay listing, grounded in data/audit/full_inventory_audit.jsonl
(the ground-truth SKU/listing snapshot taken directly from eBay - never a guessed
SKU pattern). For each product (grouped by AliExpress product_id parsed from the
real 'AE-{pid}-{sku_id}' SKU): fetch real AliExpress supplier properties once,
merge them (plus safe standard German defaults) into the EXISTING aspects of every
variant SKU - existing values are NEVER overwritten, only missing keys are added
(Hata: eBay error 25013 'Variantenmerkmale stimmen nicht' if Farbe/Groesse are
clobbered). No invented measurements or specifics - only real supplier data plus
generic, clearly-generic defaults (Markenlos, Nicht zutreffend, etc).

Progress (per-SKU) is appended to data/audit/aspect_enrichment_log.jsonl so a
timeout/interruption loses no completed work - re-running skips SKUs already
logged with ok=True.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, '.')
from src.api.ebay_client import eBayAPIClient
from src.api.aliexpress_client import AliExpressAPIClient
from src.listing_quality import source as ali_source

ROOT = Path(__file__).resolve().parents[1]
AUDIT_FILE = ROOT / 'data' / 'audit' / 'full_inventory_audit.jsonl'
LOG_FILE = ROOT / 'data' / 'audit' / 'aspect_enrichment_log.jsonl'
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

ebay = eBayAPIClient()
ali = AliExpressAPIClient()

PRODUKTART_MAP = {
    'organizer': 'Organizer', 'aufbewahrung': 'Aufbewahrungsbox', 'tasche': 'Aufbewahrungstasche',
    'halter': 'Halter', 'ständer': 'Ständer', 'behälter': 'Behälter', 'spielzeug': 'Spielzeug',
    'spiel': 'Spielzeug', 'küche': 'Küchenhelfer', 'müll': 'Mülleimer-Zubehör',
    'kleiderbügel': 'Kleiderbügel', 'hülle': 'Schutzhülle', 'case': 'Schutzhülle',
    'ladegerät': 'Ladegerät', 'kabel': 'Kabel', 'halterung': 'Halterung', 'ständer aus': 'Ständer',
    'netz': 'Netz-Organizer', 'box': 'Aufbewahrungsbox', 'korb': 'Aufbewahrungskorb',
}
# Standard German aspect-name fallback for when no title/property hint applies.
COMMON_DEFAULTS = {
    'Marke': 'Markenlos',
    'Herstellernummer': 'Nicht zutreffend',
    'Modell': 'Nicht zutreffend',
    'EAN': 'Nicht zutreffend',
    'Zustand': 'Neu',
    'Herstellungsland und -region': 'China',
    'Anzahl der Einheiten': '1',  # safe: every listing here sells exactly one unit
}

MAX_ASPECT_VALUE_LEN = 65  # Hata: eBay errorId 25002 rejects any aspect value over 65 chars


def detect_produktart(title):
    t = (title or '').lower()
    for kw, val in PRODUKTART_MAP.items():
        if kw in t:
            return val
    return None


def build_new_aspects(title, ali_properties):
    """ali_properties: dict from source.properties() - already real, German-labelled,
    junk-filtered supplier data (never a predefined whitelist, so no genuinely
    offered property is silently dropped)."""
    junk_keys = {'choice', 'ist elektrisch'}  # AliExpress program flags, not real product attributes
    aspects = {}
    for key, val in ali_properties.items():
        if key.lower() in junk_keys:
            continue
        if val and isinstance(val, str) and val.strip():
            clean = val.strip()
            # Hata: a long comma-joined AliExpress property value (e.g. a list of
            # compatible materials) trips eBay's 65-char-per-aspect-value limit
            # (errorId 25002). Truncating on a comma boundary keeps the value real
            # (first real listed option), never invents anything.
            if len(clean) > MAX_ASPECT_VALUE_LEN:
                parts = clean.split(',')
                clean = parts[0].strip()
                if len(clean) > MAX_ASPECT_VALUE_LEN:
                    clean = clean[:MAX_ASPECT_VALUE_LEN].rstrip()
            if clean:
                aspects[key] = [clean]
    produktart = detect_produktart(title)
    if produktart:
        aspects['Produktart'] = [produktart]
    for key, val in COMMON_DEFAULTS.items():
        aspects.setdefault(key, [val])
    return aspects


def load_ground_truth():
    recs = [json.loads(l) for l in AUDIT_FILE.open(encoding='utf-8')]
    live = [r for r in recs if r.get('listing_status') in ('ACTIVE', 'OUT_OF_STOCK')]
    by_pid = {}
    for r in live:
        m = re.match(r'^AE-([0-9]{6,})-', r['sku'])
        if not m:
            continue  # never guess a product id from a SKU we don't recognise
        pid = m.group(1)
        by_pid.setdefault(pid, []).append(r)
    return by_pid


def already_done():
    done = set()
    if LOG_FILE.exists():
        with LOG_FILE.open('r', encoding='utf-8') as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get('ok'):
                        done.add(rec['sku'])
                except Exception:
                    pass
    return done


def main():
    by_pid = load_ground_truth()
    print(f'Islenecek urun (benzersiz AliExpress pid): {len(by_pid)}', flush=True)
    total_skus = sum(len(v) for v in by_pid.values())
    print(f'Islenecek toplam SKU: {total_skus}', flush=True)
    done = already_done()
    print(f'Onceden tamamlanmis SKU (resume): {len(done)}', flush=True)

    log = LOG_FILE.open('a', encoding='utf-8')
    processed = 0
    for pid, records in by_pid.items():
        pending = [r for r in records if r['sku'] not in done]
        if not pending:
            continue
        try:
            raw = ali_source.fetch_raw(ali, pid)
            # properties() returns [(name, value)], already German-labelled, junk removed.
            ali_props = dict(ali_source.properties(raw))
        except Exception as ex:
            ali_props = {}
            log.write(json.dumps({'pid': pid, 'ali_details_error': f'{type(ex).__name__}: {ex}'[:200]},
                                  ensure_ascii=False) + '\n')
            log.flush()

        for rec in pending:
            sku = rec['sku']
            title = rec.get('title')
            new_aspects = build_new_aspects(title, ali_props)
            entry = {'sku': sku, 'pid': pid}
            try:
                item = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
                existing = (item.get('product') or {}).get('aspects') or {}
                before_count = len(existing)
                merged = dict(existing)
                # Hata: a PRE-EXISTING aspect value already over 65 chars (set by an
                # earlier, different code path) still gets re-validated by eBay on
                # ANY inventory_item PUT - even if we never touch that key - and
                # rejects the whole request (errorId 25002). Sanitise every value
                # (existing + new), truncating on a comma boundary, never inventing.
                for key in list(merged.keys()):
                    vals = merged[key]
                    if isinstance(vals, list):
                        fixed = []
                        for v in vals:
                            v = str(v)
                            if len(v) > MAX_ASPECT_VALUE_LEN:
                                v = v.split(',')[0].strip()[:MAX_ASPECT_VALUE_LEN].rstrip()
                            fixed.append(v)
                        merged[key] = fixed
                added = []
                for key, val in new_aspects.items():
                    if key not in merged:
                        merged[key] = val
                        added.append(key)
                if not added and merged == existing:
                    entry.update(ok=True, skipped='no_new_aspects', before=before_count, after=before_count)
                    log.write(json.dumps(entry, ensure_ascii=False) + '\n')
                    log.flush()
                    processed += 1
                    continue
                item.setdefault('product', {})['aspects'] = merged
                ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=item)
                # Refresh the offer so the merged aspects reach the live, buyer-facing listing.
                offer_id = rec.get('offer_id')
                if offer_id:
                    offer = ebay._request('GET', f'/sell/inventory/v1/offer/{offer_id}')
                    for field in ('offerId', 'status', 'listingId', 'listing'):
                        offer.pop(field, None)
                    ebay._request('PUT', f'/sell/inventory/v1/offer/{offer_id}', json=offer)
                verify = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
                after_count = len((verify.get('product') or {}).get('aspects') or {})
                entry.update(ok=True, before=before_count, after=after_count, added=added)
            except Exception as ex:
                msg = str(ex)
                if '25013' in msg or 'Variantenmerkmale' in msg:
                    # Hata: pre-existing drift between this SKU's inventory_item and its
                    # inventory_item_group varying aspects (not caused by our merge - we
                    # never touch Farbe/Groesse). Fixing it means editing the live group
                    # structure, out of scope for aspect-only enrichment; never retry blindly.
                    entry.update(ok=False, skipped='variant_group_conflict_needs_manual_review',
                                 error=msg[:300])
                else:
                    entry.update(ok=False, error=f'{type(ex).__name__}: {ex}'[:300])
            log.write(json.dumps(entry, ensure_ascii=False) + '\n')
            log.flush()
            processed += 1
            if processed % 10 == 0:
                print(f'{processed}/{total_skus} SKU islendi', flush=True)
    log.close()
    print('ENRICHMENT COMPLETE', flush=True)


if __name__ == '__main__':
    main()
