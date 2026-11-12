"""Cooperating credential writers: lock first, read latest, atomic replace.

Never break a lock automatically: a stale directory requires operator review.
All platform writers must hold the same lock through renewal and persistence.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time


@contextmanager
def credential_lock(path, timeout=10):
    lock = Path(path).with_name(Path(path).name + '.lock')
    deadline = time.monotonic() + timeout
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError('Credential configuration locked; refresh deferred') from None
            time.sleep(0.05)
    try:
        yield
    finally:
        lock.rmdir()


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def merge_credentials_locked(path, updates):
    """Caller holds credential_lock; unrelated bytes/assignments stay intact."""
    if any(not isinstance(v, str) or not v or any(c in v for c in '\r\n') for v in updates.values()):
        raise ValueError('Malformed credential')
    path = Path(path)
    text = path.read_bytes().decode('utf-8-sig') if path.exists() else ''
    merged, found = [], set()
    for line in text.splitlines(keepends=True):
        match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=', line)
        key = match.group(1) if match else None
        if key in updates:
            if key not in found:
                merged.append(key + '=' + json.dumps(updates[key]) + '\n')
                found.add(key)
        else:
            merged.append(line)
    for key in updates:
        if key not in found:
            if merged and not merged[-1].endswith('\n'):
                merged.append('\n')
            merged.append(key + '=' + json.dumps(updates[key]) + '\n')
    atomic_write(path, ''.join(merged))
