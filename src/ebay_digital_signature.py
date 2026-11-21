"""
eBay Digital Signature helper (RFC 9421 / RFC 9530) for Finances-API-class
endpoints that require it (Finances API, issueRefund, GetAccount, etc).

Private key material lives ONLY in data/.ebay_signing_key.json (chmod 600,
git-ignored) - never printed, never committed. Generated once via
POST /developer/key_management/v1/signing_key (ED25519 cipher) using the
normal OAuth bearer token - no extra user consent/scope needed, this is a
separate "signing key" concept from OAuth scopes.
"""
import base64
import hashlib
import json
import time
from pathlib import Path
from cryptography.hazmat.primitives.serialization import load_der_private_key

_KEY_PATH = Path(__file__).resolve().parents[1] / 'data' / '.ebay_signing_key.json'


def _load_signing_key():
    data = json.loads(_KEY_PATH.read_text(encoding='utf-8'))
    # eBay's "privateKey" is DER-encoded PKCS8 (48 bytes once base64-decoded
    # for an Ed25519 key, not the 32 raw seed bytes) - confirmed live by
    # inspecting the decoded length; from_private_bytes() rejects it with
    # "must be 32 bytes", load_der_private_key() is the correct loader.
    raw = base64.b64decode(data['privateKey'])
    priv = load_der_private_key(raw, password=None)
    return priv, data['jwe']


def signed_headers(method, path, authority, body=None):
    """Return the extra headers (dict) to merge into a request to an
    in-scope eBay API. `path` must be the URL path only (no query string,
    no scheme/host). `body` is the raw request body bytes/str if any."""
    priv, jwe = _load_signing_key()
    created = int(time.time())

    components = ['"x-ebay-signature-key"', '"@method"', '"@path"', '"@authority"']
    digest_header = None
    content_digest_line = ''
    if body is not None:
        body_bytes = body.encode('utf-8') if isinstance(body, str) else body
        digest = base64.b64encode(hashlib.sha256(body_bytes).digest()).decode()
        digest_header = f'sha-256=:{digest}:'
        components = ['"content-digest"'] + components
        content_digest_line = f'"content-digest": {digest_header}\n'

    sig_params = '(' + ' '.join(components) + f');created={created}'

    base_lines = (
        f'"x-ebay-signature-key": {jwe}\n'
        f'"@method": {method.upper()}\n'
        f'"@path": {path}\n'
        f'"@authority": {authority}\n'
        + content_digest_line +
        f'"@signature-params": {sig_params}'
    )
    signature = base64.b64encode(priv.sign(base_lines.encode('utf-8'))).decode()

    headers = {
        'x-ebay-signature-key': jwe,
        'Signature-Input': f'sig1={sig_params}',
        'Signature': f'sig1=:{signature}:',
        'x-ebay-enforce-signature': 'true',
    }
    if digest_header:
        headers['content-digest'] = digest_header
    return headers
