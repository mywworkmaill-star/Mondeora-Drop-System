"""Bounded local discovery memory; sampled-market cooldowns are not product bans."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import tempfile

TTL_SECONDS = 24 * 3600
MAX_ENTRIES = 512
MAX_BYTES = 512 * 1024
PAGE_CAP = 5


def policy_key(config):
    def target(key, minimum):
        try:
            value = Decimal(str(config.get(key) or minimum))
            return str(max(Decimal(minimum), value)) if value.is_finite() else minimum
        except (InvalidOperation, ValueError):
            return minimum
    policy = {'profit': target('MIN_PROFIT_EUR', '25'),
              'margin_percent': target('MIN_MARGIN_PERCENT', '25'),
              'source_cap': '40', 'reserve_per_unit': '2', 'marketplace': 'EBAY_DE',
              'destination': 'DE', 'selection_version': 1}
    return hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()


class ResearchRotation:
    def __init__(self, output_path, config, now=None):
        self.path = Path(output_path).parent / 'research_rotation.json'
        self.now = datetime.now(timezone.utc).timestamp() if now is None else now
        self.policy = policy_key(config)
        self.cursor = 0
        self.entries = []
        self.seen = []
        self.load_status = 'new'
        try:
            if self.path.stat().st_size > MAX_BYTES:
                raise ValueError('oversize')
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('schema_version') != 1:
                raise ValueError('schema')
            if data.get('policy') != self.policy:
                self.load_status = 'policy_changed'
                return
            cursor = data.get('cursor')
            if type(cursor) is not int or not 0 <= cursor < 1000000:
                raise ValueError('cursor')
            if not isinstance(data.get('entries', []), list) or not isinstance(data.get('seen', []), list):
                raise ValueError('history collections')
            self.cursor = cursor
            for row in data.get('entries', [])[:MAX_ENTRIES]:
                if self._valid(row):
                    self.entries.append(row)
            self.seen = [x for x in data.get('seen', [])[:MAX_ENTRIES]
                         if isinstance(x, str) and x.isascii() and x.isdigit()]
            self.load_status = 'loaded'
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, KeyError):
            self.entries, self.seen, self.cursor = [], [], 0
            self.load_status = 'invalid_history_reset'

    def _valid(self, row):
        return (isinstance(row, dict) and isinstance(row.get('product_id'), str)
                and row['product_id'].isascii() and row['product_id'].isdigit()
                and isinstance(row.get('sku_id'), str) and 0 < len(row['sku_id']) <= 128
                and isinstance(row.get('concept'), str) and 0 < len(row['concept']) <= 256
                and isinstance(row.get('sampled_market_query'), str)
                and len(row['sampled_market_query']) <= 512
                and row.get('reason') == 'do_not_source_at_sampled_asking_prices'
                and type(row.get('observed_at')) in (float, int)
                and self.now - TTL_SECONDS < row['observed_at'] <= self.now)

    def blocked(self, product_id, concept):
        # Product selection is deferred only for this concept/policy and TTL.
        # Selected SKU and sampled market scope remain explicit in the evidence.
        return next((row for row in self.entries
                     if row['product_id'] == product_id and row['concept'] == concept), None)

    def remember(self, item, concept, observed_at=None):
        if item.get('finance', {}).get('commercial_screen') != 'do_not_source_at_sampled_asking_prices':
            return
        row = {'product_id': str(item.get('product_id') or ''),
               'sku_id': str(item.get('sku_id') or ''), 'concept': str(concept),
               'sampled_market_query': str(item.get('market', {}).get('effective_query') or item.get('market', {}).get('query') or concept),
               'reason': 'do_not_source_at_sampled_asking_prices',
               'observed_at': self.now if observed_at is None else observed_at}
        if self._valid(row):
            self.entries = [r for r in self.entries if (r['product_id'], r['concept']) != (row['product_id'], row['concept'])]
            self.entries.append(row)
            self.entries = self.entries[-MAX_ENTRIES:]

    def seed_snapshot(self, path):
        """Explicit bounded import of schema-2 read-only evidence; never mtime as age."""
        try:
            path = Path(path)
            if path.stat().st_size > 16 * 1024 * 1024:
                return
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('schema_version') != 2 or data.get('read_only') is not True or data.get('remote_mutations_performed') is not False:
                return
            observed = datetime.fromisoformat(data['generated_at'])
            if observed.tzinfo is None:
                return
            for item in data.get('candidates', [])[:512]:
                if isinstance(item, dict):
                    # Snapshots did not record changed financial policies. Only
                    # seed the fixed original 25 EUR / 25% policy.
                    if self.policy == policy_key({}):
                        self.remember(item, item.get('keyword') or '', observed.timestamp())
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return

    def save(self, candidates):
        self.seen = list(dict.fromkeys(self.seen + [c['product_id'] for c in candidates]))[-MAX_ENTRIES:]
        self.cursor = (self.cursor + 1) % 1000000
        data = {'schema_version': 1, 'policy': self.policy, 'cursor': self.cursor,
                'entries': self.entries[-MAX_ENTRIES:], 'seen': self.seen}
        encoded = json.dumps(data, ensure_ascii=False).encode('utf-8')
        if len(encoded) > MAX_BYTES:
            raise ValueError('Research history bound exceeded')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix='.research_rotation_', suffix='.tmp', delete=False) as stream:
                name = stream.name
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
