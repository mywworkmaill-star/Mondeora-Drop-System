"""Fetch real localizedAspects for every competitor already found in
data/audit/competitor_analysis/analysis_{pid}.json, merge them per
competitor-intelligence skill rules (an aspect name/value kept only if it
appears for 50%+ of that product's competitors - avoids one-off noise),
and rewrite each analysis file with the real aspect data attached.
Progress logged to data/audit/competitor_aspect_log.jsonl (resumable).
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, '.')
from src.api.ebay_client import eBayAPIClient

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / 'data' / 'audit' / 'competitor_analysis'
LOG_FILE = ROOT / 'data' / 'audit' / 'competitor_aspect_log.jsonl'

ebay = eBayAPIClient()


def already_done():
    done = set()
    if LOG_FILE.exists():
        with LOG_FILE.open('r', encoding='utf-8') as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get('ok'):
                        done.add(rec['pid'])
                except Exception:
                    pass
    return done


def merge_aspects(per_competitor_aspects, threshold=0.5):
    """per_competitor_aspects: list of {name: value} dicts, one per competitor."""
    n = len(per_competitor_aspects)
    if not n:
        return {}
    name_values = defaultdict(Counter)
    for asp in per_competitor_aspects:
        for name, value in asp.items():
            name_values[name][value] += 1
    merged = {}
    for name, counter in name_values.items():
        value, count = counter.most_common(1)[0]
        if count / n >= threshold:
            merged[name] = {'value': value, 'competitors_with_this_value': count, 'of': n}
    return merged


def main():
    files = sorted(ANALYSIS_DIR.glob('analysis_*.json'))
    print(f'Islenecek urun dosyasi: {len(files)}', flush=True)
    done = already_done()
    print(f'Onceden tamamlanmis (resume): {len(done)}', flush=True)
    log = LOG_FILE.open('a', encoding='utf-8')
    for i, f in enumerate(files):
        data = json.loads(f.read_text(encoding='utf-8'))
        pid = data['product_id']
        if pid in done:
            continue
        entry = {'pid': pid}
        try:
            per_competitor = []
            for comp in data.get('competitors', []):
                item_id = comp.get('item_id')
                if not item_id:
                    continue
                try:
                    r = ebay._request('GET', f'/buy/browse/v1/item/{quote(item_id, safe="")}')
                    la = r.get('localizedAspects') or []
                    aspects = {a.get('name'): a.get('value') for a in la if a.get('name') and a.get('value')}
                except Exception as ex:
                    aspects = {}
                    comp['aspect_fetch_error'] = f'{type(ex).__name__}: {ex}'[:150]
                comp['aspects'] = aspects
                comp['aspect_count'] = len(aspects)
                per_competitor.append(aspects)
            merged = merge_aspects(per_competitor, threshold=0.5)
            data['merged_competitor_aspects'] = merged
            data['merged_aspect_count'] = len(merged)
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            entry.update(ok=True, merged_aspect_count=len(merged))
        except Exception as ex:
            entry.update(ok=False, error=f'{type(ex).__name__}: {ex}'[:300])
        log.write(json.dumps(entry, ensure_ascii=False) + '\n')
        log.flush()
        if (i + 1) % 5 == 0:
            print(f'{i + 1}/{len(files)} urun islendi', flush=True)
    log.close()
    print('COMPETITOR ASPECT FETCH COMPLETE', flush=True)


if __name__ == '__main__':
    main()
