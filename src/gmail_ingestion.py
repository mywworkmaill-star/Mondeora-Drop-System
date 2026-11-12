"""Bounded read-only Gmail REST intake; OAuth transport is NOT sender evidence.

Explicit local config: EMAIL_INGESTION_ENABLED=true, EMAIL_GMAIL_ENABLED=true,
EMAIL_GMAIL_CREDENTIALS_FILE=<absolute authorized_user JSON path>, and
EMAIL_GMAIL_EXPECTED_ACCOUNT=<exact account>. No credential discovery or writes.
The user must independently authorize their own OAuth client with gmail.readonly.

Each cycle reads ONE bounded recent search window (default newer_than:7d), not a
complete inbox/history cursor. Older/backlogged mail needs a scoped query or EML
import. Existing DB unique exact-raw SHA256 deduplicates across cycles/transports;
no provider IDs, mailbox subjects, bodies or tokens are persisted here. Re-reading
also permits independent source attestations to be refreshed by the existing store.
"""
import base64
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any

import requests

from src.email_tracking import EmailTrackingHint, MAX_MESSAGES, MAX_MESSAGE_BYTES, _store

API = 'https://gmail.googleapis.com/gmail/v1/users/me'
TOKEN = 'https://oauth2.googleapis.com/token'
MAX_JSON_BYTES = 4 * ((MAX_MESSAGE_BYTES + 2) // 3) + 8192


class GmailFailure(Exception):
    """Allowlisted machine status only; never include provider responses."""


def _request_json(http, method, url, deadline, *, cap=65536, **kwargs):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise GmailFailure('gmail_time_budget_exceeded')
    response = http.request(method, url, timeout=(min(5, remaining), min(10, remaining)),
                            allow_redirects=False, verify=True, stream=True, **kwargs)
    try:
        if response.status_code in (401, 403) or (url == TOKEN and response.status_code == 400):
            raise GmailFailure('gmail_authorization_required')
        if 300 <= response.status_code < 400:
            raise GmailFailure('gmail_redirect_rejected')
        if response.status_code != 200:
            raise GmailFailure('gmail_read_failed')
        length = response.headers.get('Content-Length')
        if length is not None and (not length.isdecimal() or int(length) > cap):
            raise GmailFailure('gmail_response_too_large')
        chunks = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            if time.monotonic() > deadline:
                raise GmailFailure('gmail_time_budget_exceeded')
            chunks.extend(chunk)
            if len(chunks) > cap:
                raise GmailFailure('gmail_response_too_large')
        result = json.loads(chunks)
        if not isinstance(result, dict) or 'error' in result:
            raise GmailFailure('gmail_invalid_response')
        return result
    finally:
        response.close()


def _credentials(config):
    path = Path(config['EMAIL_GMAIL_CREDENTIALS_FILE'])
    if not path.is_absolute() or path.is_symlink():
        raise GmailFailure('gmail_invalid_credentials_path')
    try:
        with path.open('rb') as handle:
            raw = handle.read(16385)
    except OSError:
        raise GmailFailure('gmail_credentials_unavailable') from None
    if len(raw) > 16384:
        raise GmailFailure('gmail_unsupported_credentials')
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise GmailFailure('gmail_unsupported_credentials') from None
    if (not isinstance(value, dict) or value.get('type') != 'authorized_user'
            or not all(isinstance(value.get(k), str) and 0 < len(value[k]) <= 8192
                       for k in ('client_id', 'client_secret', 'refresh_token'))):
        raise GmailFailure('gmail_unsupported_credentials')
    return {k: value[k] for k in ('client_id', 'client_secret', 'refresh_token')}


def _raw_message(value, message_id):
    encoded = value.get('raw')
    if value.get('id') != message_id or not isinstance(encoded, str) or not encoded:
        raise ValueError('invalid_raw_message')
    if len(encoded) > 4 * ((MAX_MESSAGE_BYTES + 2) // 3):
        raise ValueError('message_size_exceeded')
    # Reject non-URL-safe alphabet, interior/excess padding and ambiguous encodings.
    if not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}', encoded):
        raise ValueError('invalid_raw_base64')
    raw = base64.b64decode(encoded + '=' * (-len(encoded) % 4), altchars=b'-_', validate=True)
    if (len(raw) > MAX_MESSAGE_BYTES or not raw
            or base64.urlsafe_b64encode(raw).decode().rstrip('=') != encoded.rstrip('=')):
        raise ValueError('invalid_raw_message')
    return raw


def ingest_gmail(session, config, *, limit=10):
    """Read profile, list one window, get exact raw, stage hints; never mutate mail.

    Separate transport status/held counts; failures never authorize shipment.
    Refresh once at cycle start, transient token only, fresh local file each cycle.
    """
    stats: dict[str, Any] = dict(status='gmail_disabled', checked=0, stored=0, duplicates=0,
                 rejected=0, held=0, mailbox_verified=False)
    if not all(str(config.get(k, '')).lower() == 'true'
               for k in ('EMAIL_INGESTION_ENABLED', 'EMAIL_GMAIL_ENABLED')):
        return stats
    if not all(config.get(k) for k in ('EMAIL_GMAIL_CREDENTIALS_FILE', 'EMAIL_GMAIL_EXPECTED_ACCOUNT')):
        stats['status'] = 'gmail_not_configured'
        return stats
    http = None
    try:
        expected = config['EMAIL_GMAIL_EXPECTED_ACCOUNT']
        query = config.get('EMAIL_GMAIL_QUERY', 'newer_than:7d')
        if (type(limit) is not int or not 1 <= limit <= MAX_MESSAGES
                or not isinstance(expected, str) or not re.fullmatch(r'[^\s@]{1,64}@[^\s@]{1,190}', expected)
                or not isinstance(query, str) or not 1 <= len(query) <= 512
                or any(ord(c) < 32 for c in query)):
            raise GmailFailure('gmail_invalid_configuration')
        credentials = _credentials(config)
        deadline = time.monotonic() + 60
        http = requests.Session()
        http.trust_env = False  # Do not route OAuth secrets through environment proxies.
        token = _request_json(http, 'POST', TOKEN, deadline,
                              data=dict(credentials, grant_type='refresh_token'))
        access = token.get('access_token')
        if (not isinstance(access, str) or not 1 <= len(access) <= 8192
                or any(ord(c) <= 32 or ord(c) >= 127 for c in access)
                or str(token.get('token_type', '')).lower() != 'bearer'):
            raise GmailFailure('gmail_authorization_required')
        headers = {'Authorization': 'Bearer ' + access}
        profile = _request_json(http, 'GET', API + '/profile', deadline, headers=headers)
        actual = profile.get('emailAddress')
        if not isinstance(actual, str) or actual.casefold() != expected.casefold():
            raise GmailFailure('gmail_account_mismatch')
        window = _request_json(http, 'GET', API + '/messages', deadline, headers=headers,
                               params={'maxResults': limit, 'q': query, 'includeSpamTrash': 'false'})
        messages = window.get('messages', [])
        if not isinstance(messages, list) or len(messages) > limit:
            raise GmailFailure('gmail_invalid_response')
        ids = []
        for message in messages:
            message_id = message.get('id') if isinstance(message, dict) else None
            if not isinstance(message_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', message_id):
                raise GmailFailure('gmail_invalid_response')
            if message_id not in ids:
                ids.append(message_id)
        EmailTrackingHint.__table__.create(session.get_bind(), checkfirst=True)
        for message_id in ids:
            stats['checked'] += 1
            value = _request_json(http, 'GET', API + '/messages/' + message_id, deadline,
                                  cap=MAX_JSON_BYTES, headers=headers, params={'format': 'raw'})
            try:
                raw = _raw_message(value, message_id)
                _store(session, raw, config, stats)
                hint = session.query(EmailTrackingHint).filter_by(message_hash=hashlib.sha256(raw).hexdigest()).one()
                if not hint.source_authenticated or hint.reason != 'awaiting_api_reconciliation':
                    stats['held'] += 1
            except Exception:
                session.rollback()
                stats['rejected'] += 1
        stats['status'] = 'read_only' if not stats['rejected'] else 'gmail_messages_rejected'
        stats['mailbox_verified'] = not bool(stats['rejected'])
    except GmailFailure as exc:
        stats['status'] = str(exc)
    except Exception:
        stats['status'] = 'gmail_read_failed'
    finally:
        if http is not None:
            http.close()
    return stats
