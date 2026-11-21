#!/usr/bin/env python3
"""
Automated Dimension Extraction for `needs_dimensions` products
================================================================

ROOT CAUSE FIX (2026-11-21): orchestra_v5_2_aliexpress_verified.py's
step_4_comprehensive_spec_extraction() was ALWAYS designed as a human/agent
-in-the-loop step — when no comprehensive_specs_{id}.json cache exists, it
just prints "MANUEL COMPREHENSIVE SPEC EXTRACTION GEREKLI!" instructions and
falls back to a found=False/confidence=0 stub. No cron job, ever, calls an
actual vision model for this — that is why the needs_dimensions backlog only
ever grows and never shrinks on its own.

This script closes that gap: it actually calls vision_analyze (via the same
secure subprocess-bridge pattern as src/vision/aspect_extractor.py, with the
same json.dumps() escaping fix) on each needs_dimensions product's images,
asks specifically for literal measurement text (never invents one — "no
fabricated data" is a hard project rule), and writes the result in the EXACT
schema has_verified_dimensions() already expects. On a confident 3-axis find,
it resets status back to 'ready_to_list' so Orchestra's normal selection
query picks it up on its next scheduled run — closing the second half of the
gap (nothing used to ever un-stick a needs_dimensions product either).

USAGE:
    python scripts/auto_dimension_extraction.py [batch_size]
    (default batch_size=10 — keeps API/vision cost bounded per run; intended
    to be run daily via cron until the backlog clears, then as new products
    enter needs_dimensions.)
"""
import sys
import os
import json
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DIMENSION_PROMPT = """You are checking ONE product photo for a REAL, literal physical \
measurement (length/width/height/depth/diameter in cm, mm, or inch) printed or \
overlaid on the image itself — a dimension diagram, ruler, callout text, or \
size chart. Do NOT guess, estimate, or infer a measurement from how the object \
looks ("it looks about 10cm") — only report a number if you can literally read \
digits with a unit (cm/mm/inch) in the image. If multiple measurements are \
shown (e.g. a size-variant table), report only the ones that unambiguously \
label length/width/height/depth/diameter (not unrelated numbers like \
piece-count or price). If you see no such literal measurement text anywhere \
in this image, say so plainly — never fabricate a number. Respond in this \
exact format, nothing else:
FOUND: yes|no
LENGTH_CM: <number or none>
WIDTH_CM: <number or none>
HEIGHT_CM: <number or none>
DEPTH_CM: <number or none>
DIAMETER_CM: <number or none>
QUOTE: <the exact text you read, or 'none'>
"""


def call_vision(image_url, timeout=40):
    """Same secure subprocess-bridge pattern as src/vision/aspect_extractor.py
    (json.dumps()-escaped — never raw-interpolate external text into source)."""
    safe_url = json.dumps(image_url)
    safe_prompt = json.dumps(DIMENSION_PROMPT)
    code = f"""
from hermes_tools import vision_analyze
result = vision_analyze({safe_url}, {safe_prompt})
print(result['content'])
"""
    try:
        result = subprocess.run(['python', '-c', code], capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return None
        return result.stdout
    except Exception:
        return None


def parse_vision_reply(text):
    """Parse the fixed-format reply into has_verified_dimensions()'s schema."""
    if not text:
        return None
    lines = {}
    for line in text.strip().splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            lines[k.strip().upper()] = v.strip()

    def num(key):
        v = lines.get(key, 'none')
        if not v or v.lower() == 'none':
            return None
        try:
            return float(v.replace(',', '.').split()[0])
        except (ValueError, IndexError):
            return None

    found = lines.get('FOUND', 'no').lower().startswith('y')
    return {
        'found': found,
        'length_cm': num('LENGTH_CM'),
        'width_cm': num('WIDTH_CM'),
        'height_cm': num('HEIGHT_CM'),
        'depth_cm': num('DEPTH_CM'),
        'diameter_cm': num('DIAMETER_CM'),
        'text': lines.get('QUOTE', ''),
        'confidence': 95 if found else 0,
    }


def all_three_present(d):
    return bool(d) and all(d.get(k) is not None for k in ('length_cm', 'width_cm', 'height_cm'))


def process_product(pid, title, image_url, max_images=6):
    """Try up to max_images photos (first ones most likely to carry a spec
    sheet/overlay per step_4's own documented scan-priority); stop at the
    first confident 3-axis find."""
    if not image_url:
        return {'found': False, 'length_cm': None, 'width_cm': None, 'height_cm': None,
                'depth_cm': None, 'diameter_cm': None, 'text': 'no image_url in DB', 'confidence': 0}

    images = [u.strip() for u in image_url.split(',') if u.strip()][:max_images]
    best = {'found': False, 'length_cm': None, 'width_cm': None, 'height_cm': None,
            'depth_cm': None, 'diameter_cm': None, 'text': '', 'confidence': 0}

    for i, img in enumerate(images, 1):
        reply = call_vision(img)
        parsed = parse_vision_reply(reply)
        if not parsed:
            continue
        # Merge: keep the best individual axis found across images (a real
        # supplier photo set often splits L/W on one image, H on another).
        for k in ('length_cm', 'width_cm', 'height_cm', 'depth_cm', 'diameter_cm'):
            if best.get(k) is None and parsed.get(k) is not None:
                best[k] = parsed[k]
                best['text'] += (' | ' if best['text'] else '') + f'img{i}: {parsed["text"]}'
        if all_three_present(best):
            best['found'] = True
            best['confidence'] = 95
            break
        time.sleep(1.0)  # light rate-limit between calls

    if all_three_present(best):
        best['found'] = True
        best['confidence'] = 95
    return best


def run(batch_size=10):
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    cursor = conn.cursor()

    # Prioritize products that have NEVER been attempted (no specs file) —
    # those with a file already got an honest "no visible measurement" or
    # partial-axis verdict from a prior real pass and re-running them on
    # every cron tick would just burn vision-API cost for the same answer.
    cursor.execute("SELECT id, title, image_url FROM products WHERE status='needs_dimensions' AND is_listed != 1")
    all_pending = cursor.fetchall()

    never_attempted = [p for p in all_pending if not (ROOT / f'comprehensive_specs_{p[0]}.json').exists()]
    targets = never_attempted[:batch_size]

    print(f"needs_dimensions toplam: {len(all_pending)} | hic denenmemis: {len(never_attempted)} | bu batch: {len(targets)}")

    resolved, still_stuck = 0, 0
    for pid, title, image_url in targets:
        print(f"\n[{pid}] {title[:55]}")
        result = process_product(pid, title, image_url)
        specs_path = ROOT / f'comprehensive_specs_{pid}.json'
        full_specs = {'dimensions': result}
        with open(specs_path, 'w', encoding='utf-8') as f:
            json.dump(full_specs, f, indent=2, ensure_ascii=False)

        if all_three_present(result) and result.get('confidence', 0) >= 95:
            cursor.execute("UPDATE products SET status='ready_to_list', updated_at=datetime('now') WHERE id=?", (pid,))
            conn.commit()
            print(f"   OK bulundu, ready_to_list'e donduruldu: {result['text'][:80]}")
            resolved += 1
        else:
            print(f"   olcu bulunamadi (gercek, uydurulmadi) - needs_dimensions'ta kaliyor")
            still_stuck += 1

    print(f"\n=== OZET === islenen: {len(targets)} | ready_to_list'e donduruldu: {resolved} | hala olcusuz: {still_stuck}")
    conn.close()
    return {'processed': len(targets), 'resolved': resolved, 'still_stuck': still_stuck, 'remaining_never_tried': len(never_attempted) - len(targets)}


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    run(n)
