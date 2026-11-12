"""Persistent vector memory (SQLite + numpy). Works offline.

Default embedder: hashed word + char-trigram vectors (no model download, deterministic).
If MEMORY_EMBEDDINGS=openai and OPENAI_API_KEY exist, OpenAI embeddings are used instead;
any failure falls back to the offline embedder. Vectors from different embedders are never
mixed: each row stores its embedder name and search only compares matching rows.

Never store secrets: text is passed through `scrub` before it is saved.
"""
import hashlib
import json
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / 'data' / 'memory_vectors.db'
DIM = 512
_SECRET = re.compile(r'(v\^1\.1#[^\s"\']+|eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.?[A-Za-z0-9_\-]*'
                     r'|(?i:(?:token|secret|password|api[_-]?key)\s*[=:]\s*)[^\s"\',}]{6,})')


def scrub(text):
    return _SECRET.sub('[REDACTED]', text or '')


def _tokens(text):
    words = re.findall(r'\w+', text.lower())
    grams = []
    for w in words:
        padded = f'#{w}#'
        grams += [padded[i:i + 3] for i in range(max(1, len(padded) - 2))]
    return words + grams


def hash_embed(text):
    v = np.zeros(DIM, dtype=np.float32)
    for tok in _tokens(text):
        h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), 'little')
        v[h % DIM] += 1.0 if (h >> 63) & 1 else -1.0
    n = np.linalg.norm(v)
    return v / n if n else v


def _openai_embed(text):
    import os
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise RuntimeError('no key')
    from openai import OpenAI
    out = OpenAI(api_key=key, timeout=20).embeddings.create(model='text-embedding-3-small', input=text[:6000])
    v = np.array(out.data[0].embedding, dtype=np.float32)
    return v / (np.linalg.norm(v) or 1)


class MemoryStore:
    def __init__(self, path=None, embedder=None):
        self.path = Path(path or DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder  # None -> auto (offline unless configured)
        with closing(self._db()) as db:
            db.execute('''create table if not exists memory (
                id integer primary key, key text unique, kind text, text text, meta text,
                embedder text, vec blob, created real, hits integer default 0)''')
            db.execute('create index if not exists ix_kind on memory(kind)')
            db.commit()

    def _db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute('pragma journal_mode=wal')
        return db

    def _embed(self, text):
        if self.embedder is not None:
            return 'custom', np.asarray(self.embedder(text), dtype=np.float32)
        import os
        if os.environ.get('MEMORY_EMBEDDINGS', '').lower() == 'openai':
            try:
                return 'openai', _openai_embed(text)
            except Exception:
                pass
        return 'hash', hash_embed(text)

    def add(self, kind, text, meta=None, key=None):
        """Insert or refresh one memory. `key` makes it idempotent (same key -> overwritten)."""
        text = scrub(text).strip()
        if not text:
            return None
        key = key or hashlib.sha1(f'{kind}\n{text}'.encode()).hexdigest()
        name, vec = self._embed(text)
        with closing(self._db()) as db:
            db.execute('''insert into memory (key,kind,text,meta,embedder,vec,created) values (?,?,?,?,?,?,?)
                on conflict(key) do update set text=excluded.text, meta=excluded.meta,
                embedder=excluded.embedder, vec=excluded.vec, created=excluded.created''',
                       (key, kind, text, json.dumps(meta or {}, default=str), name, vec.tobytes(), time.time()))
            db.commit()
        return key

    def search(self, query, k=5, kind=None, min_score=0.15):
        name, q = self._embed(scrub(query))
        sql, args = 'select id,kind,text,meta,vec,created from memory where embedder=?', [name]
        if kind:
            sql += ' and kind=?'; args.append(kind)
        with closing(self._db()) as db:
            rows = db.execute(sql, args).fetchall()
            scored = []
            for id_, kd, text, meta, blob, created in rows:
                v = np.frombuffer(blob, dtype=np.float32)
                if v.shape != q.shape:
                    continue
                score = float(v @ q)
                score += 0.02 * min(1.0, 86400 * 30 / max(time.time() - created, 1))  # slight recency boost
                if score >= min_score:
                    scored.append((score, id_, kd, text, json.loads(meta or '{}')))
            scored.sort(key=lambda r: -r[0])
            top = scored[:k]
            for s in top:
                db.execute('update memory set hits=hits+1 where id=?', (s[1],))
            db.commit()
        return [{'score': round(s, 3), 'kind': kd, 'text': t, 'meta': m} for s, _, kd, t, m in top]

    def context_for(self, query, k=4, max_chars=1800):
        """Compact context block to prepend to an LLM prompt or a heal decision."""
        out, used = [], 0
        for r in self.search(query, k=k):
            line = f"[{r['kind']} {r['score']}] {r['text'][:500]}"
            if used + len(line) > max_chars:
                break
            out.append(line); used += len(line)
        return '\n'.join(out)

    def stats(self):
        with closing(self._db()) as db:
            return dict(db.execute('select kind,count(*) from memory group by kind').fetchall())

    # ---------- project indexing ----------
    def index_project(self, root=ROOT, max_docs=200):
        counts = {'docs': 0, 'incidents': 0, 'products': 0}
        for p in list(Path(root).glob('*.md'))[:max_docs]:
            try:
                text = p.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            for i, chunk in enumerate(_chunks(text)):
                self.add('doc', f'{p.name}: {chunk}', {'file': p.name, 'chunk': i}, key=f'doc:{p.name}:{i}')
                counts['docs'] += 1
        db_file = Path(root) / 'data' / 'dropshipping.db'
        if db_file.exists():
            with closing(sqlite3.connect(f'file:{db_file.as_posix()}?mode=ro', uri=True)) as db:
                for r in db.execute("select sync_type,status,error_message,started_at from sync_logs "
                                    "where status not in ('success','ok') order by id desc limit 200"):
                    self.add('incident', f'{r[0]} {r[1]} {r[2] or ""}', {'at': r[3]},
                             key=f'synclog:{r[0]}:{r[3]}')
                    counts['incidents'] += 1
                for r in db.execute('select coalesce(aliexpress_product_id,ebay_item_id),title,status,aliexpress_price,ebay_price,category_id from products'):
                    self.add('product', f'product {r[0]} "{r[1]}" status={r[2]} cost={r[3]} price={r[4]} category={r[5]}',
                             {'ali_id': r[0]}, key=f'product:{r[0] or r[1]}')
                    counts['products'] += 1
        return counts


def _chunks(text, size=700):
    paras, cur, out = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()], '', []
    for p in paras:
        if len(cur) + len(p) > size and cur:
            out.append(cur); cur = ''
        cur += ('\n' if cur else '') + p
    if cur:
        out.append(cur)
    return out[:40]


_default = None


def get_memory():
    global _default
    if _default is None:
        _default = MemoryStore()
    return _default
