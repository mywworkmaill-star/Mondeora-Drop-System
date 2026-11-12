"""Read-only email tracking hints. Mail text never authorizes shipment or upload.

Run: python -m src.email_tracking [--eml-folder PATH] [--imap]
Configuration is read from the project's .env, never inferred from an address.
Source authentication requires an EXTERNAL verifier's SHA256 allowlist in
EMAIL_SOURCE_VERIFIED_SHA256. From/Authentication-Results headers alone prove
nothing; this module deliberately does not implement a DKIM verifier.
"""
import argparse
import hashlib
import imaplib
import json
import re
import ssl
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path

from sqlalchemy import Boolean, Column, Integer, String, create_engine, or_
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, DATABASE_URL, OrderLine, PROJECT_ROOT

MAX_MESSAGE_BYTES = 262144
MAX_MESSAGES = 50


class EmailTrackingHint(Base):
    __tablename__ = 'email_tracking_hints'
    id = Column(Integer, primary_key=True)
    message_hash = Column(String(64), unique=True, nullable=False)
    message_id_hash = Column(String(64), index=True)
    supplier_order_id = Column(String(100), index=True)
    tracking_number = Column(String(200))
    carrier = Column(String(80))
    source_authenticated = Column(Boolean, nullable=False, default=False)
    reason = Column(String(80), nullable=False)
    reconciliation_state = Column(String(80), nullable=False, default='staged')
    order_line_id = Column(Integer)


def _json(config, key, default):
    value = config.get(key, default)
    return json.loads(value) if isinstance(value, str) else value


def parse_message(raw, config):
    """Extract labelled fields only, no links, attachments or mail instructions."""
    if not isinstance(raw, bytes) or len(raw) > MAX_MESSAGE_BYTES:
        raise ValueError('message_size_exceeded')
    digest = hashlib.sha256(raw).hexdigest()
    message = BytesParser(policy=policy.default).parsebytes(raw)
    result = dict(message_hash=digest, message_id_hash=None, supplier_order_id=None,
                  tracking_number=None, carrier=None, source_authenticated=False,
                  reason='unsupported_email_format')
    mids = message.get_all('Message-ID', [])
    if len(mids) == 1:
        result['message_id_hash'] = hashlib.sha256(str(mids[0]).encode()).hexdigest()
    texts = []
    for part in message.walk():
        if part.get_content_type() == 'text/plain' and part.get_content_disposition() != 'attachment':
            payload = part.get_payload(decode=True) or b''
            if not isinstance(payload, bytes):
                raise ValueError('unsupported_email_payload')
            texts.append(payload.decode(part.get_content_charset() or 'utf-8', errors='replace'))
    text = '\n'.join(texts)
    # Full-line fields keep narrative/instruction text outside the data grammar.
    orders = re.findall(r'^\s*(?:Supplier order ID|Order ID|Order number|Bestellnummer|Sipari[sş] no)\s*[:#]\s*([0-9]{1,100})\s*$', text, re.M | re.I)
    tracks = re.findall(r'^\s*(?:Tracking number|Tracking no|Sendungsnummer|Takip no)\s*[:#]\s*([A-Za-z0-9-]{5,200})\s*$', text, re.M | re.I)
    carriers = re.findall(r'^\s*(?:Carrier|Shipping carrier|Versanddienstleister)\s*:\s*([^\r\n]{1,80})\s*$', text, re.M | re.I)
    if len(set(orders)) == 1:
        result['supplier_order_id'] = orders[0]
    labelled_orders = re.findall(r'^\s*(?:Supplier order ID|Order ID|Order number|Bestellnummer|Sipari[sş] no)\s*[:#]', text, re.M | re.I)
    labelled_tracks = re.findall(r'^\s*(?:Tracking number|Tracking no|Sendungsnummer|Takip no)\s*[:#]', text, re.M | re.I)
    if len(labelled_orders) != len(orders) or len(labelled_tracks) != len(tracks):
        result['reason'] = 'malformed_or_ambiguous_fields'
        return result
    if len(set(orders)) > 1:
        result['reason'] = 'conflicting_supplier_order_ids'
        return result
    if not orders or not tracks or not carriers:
        return result
    if len(tracks) != 1 or len(carriers) != 1:
        result['reason'] = 'multiple_packages_or_fields'
        return result
    result['tracking_number'] = tracks[0]
    mapping = _json(config, 'TRACKING_CARRIER_MAP', {})
    carrier = mapping.get(carriers[0].strip()) if isinstance(mapping, dict) else None
    if not isinstance(carrier, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', carrier):
        result['reason'] = 'unknown_carrier'
        return result
    result['carrier'] = carrier
    senders = getaddresses([str(v) for v in message.get_all('From', [])])
    allowed = _json(config, 'EMAIL_SUPPLIER_SENDERS', [])
    if (not isinstance(allowed, list) or len(senders) != 1
            or senders[0][1].lower() not in [str(v).lower() for v in allowed]):
        result['reason'] = 'supplier_sender_not_allowlisted'
        return result
    authenticated = _json(config, 'EMAIL_SOURCE_VERIFIED_SHA256', [])
    result['source_authenticated'] = isinstance(authenticated, list) and digest in authenticated
    result['reason'] = 'awaiting_api_reconciliation' if result['source_authenticated'] else 'source_authentication_required'
    return result


def _store(session, raw, config, stats):
    hint = parse_message(raw, config)
    existing = session.query(EmailTrackingHint).filter_by(message_hash=hint['message_hash']).first()
    if existing:
        # Refresh external source attestations without appending duplicate evidence.
        for key, value in hint.items():
            setattr(existing, key, value)
        existing.reconciliation_state = 'staged'
        session.commit()
        stats['duplicates'] += 1
        return
    session.add(EmailTrackingHint(**hint))
    session.commit()
    stats['stored'] += 1


def ingest_folder(session, folder, config, limit=MAX_MESSAGES):
    """Bounded nonrecursive .eml intake; never persist paths, bodies or recipients."""
    EmailTrackingHint.__table__.create(session.get_bind(), checkfirst=True)
    stats = {'checked': 0, 'stored': 0, 'duplicates': 0, 'rejected': 0}
    if type(limit) is not int or not 1 <= limit <= MAX_MESSAGES:
        raise ValueError('invalid_message_limit')
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError('eml_folder_unavailable')
    for path in folder.iterdir():
        if stats['checked'] >= limit:
            break
        if path.suffix.lower() != '.eml' or path.is_symlink() or not path.is_file():
            continue
        stats['checked'] += 1
        try:
            with path.open('rb') as handle:
                raw = handle.read(MAX_MESSAGE_BYTES + 1)
            _store(session, raw, config, stats)
        except Exception:
            session.rollback()
            stats['rejected'] += 1
    return stats


def reconcile_email_hints(session, line, tracking, carrier):
    """Called ONLY after supplier shipment AND exact eBay paid-line validation.

    Returns no tracking: the existing verified API path retains sole authority.
    Staged mail can veto a conflict, never substitute a number or authorize POST.
    """
    EmailTrackingHint.__table__.create(session.get_bind(), checkfirst=True)
    hints = session.query(EmailTrackingHint).filter(or_(
        EmailTrackingHint.supplier_order_id == line.aliexpress_order_id,
        EmailTrackingHint.reason == 'conflicting_supplier_order_ids')).all()
    blocked = False
    for hint in hints:
        # Unattributable conflicts hold uploads; never invent an order binding.
        hint.order_line_id = line.id if hint.supplier_order_id == line.aliexpress_order_id else None
        if not hint.source_authenticated:
            hint.reconciliation_state = 'blocked_source_authentication'
            blocked = True
        elif hint.reason != 'awaiting_api_reconciliation':
            hint.reconciliation_state = 'blocked_email_evidence'
            blocked = True
        elif (hint.tracking_number, hint.carrier) != (tracking, carrier):
            hint.reconciliation_state = 'blocked_api_mismatch'
            blocked = True
        else:
            hint.reconciliation_state = 'api_matched'
    session.flush()
    if blocked:
        raise ValueError('email_tracking_evidence_blocked')


def ingest_imap(session, config, *, enabled=False, limit=MAX_MESSAGES):
    """Explicit opt-in TLS/EXAMINE/PEEK only; last bounded UID window, no writes.

    Window polling may leave older messages unread; export those to .eml intake.
    Credentials must already exist in local configuration, not in CLI arguments.
    """
    if not enabled:
        return {'status': 'imap_disabled'}
    if not all(config.get(k) for k in ('EMAIL_IMAP_HOST', 'EMAIL_IMAP_USERNAME', 'EMAIL_IMAP_PASSWORD')):
        return {'status': 'mailbox_not_configured'}
    stats = {'status': 'read_only', 'checked': 0, 'stored': 0, 'duplicates': 0, 'rejected': 0}
    mail = None
    try:
        if type(limit) is not int or not 1 <= limit <= MAX_MESSAGES:
            raise ValueError('invalid_message_limit')
        port = int(config.get('EMAIL_IMAP_PORT', 993))
        if not 1 <= port <= 65535:
            raise ValueError('invalid_port')
        mail = imaplib.IMAP4_SSL(config['EMAIL_IMAP_HOST'], port,
                                ssl_context=ssl.create_default_context(), timeout=15)
        if mail.login(config['EMAIL_IMAP_USERNAME'], config['EMAIL_IMAP_PASSWORD'])[0] != 'OK':
            raise ValueError('imap_login_failed')
        folder = config.get('EMAIL_IMAP_FOLDER', 'INBOX')
        if not isinstance(folder, str) or not re.fullmatch(r'[A-Za-z0-9_./ -]{1,100}', folder):
            raise ValueError('invalid_folder')
        if mail.select('"' + folder + '"', readonly=True)[0] != 'OK':
            raise ValueError('imap_select_failed')
        status, data = mail.status('"' + folder + '"', '(UIDNEXT)')
        match = re.search(rb'UIDNEXT\s+([0-9]+)', b' '.join(data)) if status == 'OK' else None
        if not match:
            raise ValueError('imap_uid_window_unavailable')
        next_uid = int(match.group(1))
        EmailTrackingHint.__table__.create(session.get_bind(), checkfirst=True)
        for uid in range(max(1, next_uid - limit), next_uid):
            status, data = mail.uid('FETCH', str(uid), f'(RFC822.SIZE BODY.PEEK[]<0.{MAX_MESSAGE_BYTES + 1}>)')
            if status != 'OK':
                raise ValueError('imap_fetch_failed')
            chunks = [v for v in data if isinstance(v, tuple) and len(v) == 2 and isinstance(v[1], bytes)]
            if not chunks:
                continue
            stats['checked'] += 1
            try:
                if len(chunks) != 1:
                    raise ValueError('ambiguous_message')
                size = re.search(rb'RFC822.SIZE\s+([0-9]+)', chunks[0][0])
                if not size or int(size.group(1)) > MAX_MESSAGE_BYTES:
                    raise ValueError('message_size_exceeded')
                _store(session, chunks[0][1], config, stats)
            except Exception:
                session.rollback()
                stats['rejected'] += 1
    except Exception:
        stats['status'] = 'imap_read_failed'
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                pass
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=PROJECT_ROOT / '.env')
    parser.add_argument('--eml-folder', type=Path)
    parser.add_argument('--imap', action='store_true', help='Explicitly enable bounded read-only IMAP intake')
    parser.add_argument('--gmail', action='store_true', help='Probe configured bounded read-only Gmail intake; both config opt-ins still required')
    args = parser.parse_args(argv)
    engine = None
    try:
        from dotenv import dotenv_values
        config = dict(dotenv_values(args.config))
        folder = args.eml_folder or Path(config.get('EMAIL_EML_FOLDER') or PROJECT_ROOT / 'data/email_tracking/inbox')
        if not folder.is_absolute():
            folder = PROJECT_ROOT / folder
        folder.mkdir(parents=True, exist_ok=True)
        db_url = config.get('DATABASE_URL') or DATABASE_URL
        from sqlalchemy.engine import make_url
        url = make_url(db_url)
        if url.drivername.startswith('sqlite') and url.database not in (None, '', ':memory:'):
            db_path = Path(url.database)
            if not db_path.is_absolute():
                db_path = PROJECT_ROOT / db_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
            url = url.set(database=str(db_path))
        engine = create_engine(url)
        with sessionmaker(bind=engine)() as session:
            report = {'local': ingest_folder(session, folder, config),
                      'imap': ingest_imap(session, config, enabled=args.imap),
                      'mailbox_verified': False, 'shipment_verified_by_email': False,
                      'uploads_attempted': 0}
            if args.gmail:
                from src.gmail_ingestion import ingest_gmail
                report['gmail'] = ingest_gmail(session, config)
        report['mailbox_verified'] = (report['imap'].get('status') == 'read_only'
                                      or report.get('gmail', {}).get('mailbox_verified', False))
        print(json.dumps(report, sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({'status': 'email_ingestion_failed', 'mailbox_verified': False, 'uploads_attempted': 0}))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    # Gmail reuses these models/store. Running -m must not register them twice
    # under both __main__ and the canonical import name.
    import sys
    sys.modules.setdefault('src.email_tracking', sys.modules[__name__])
    raise SystemExit(main())

