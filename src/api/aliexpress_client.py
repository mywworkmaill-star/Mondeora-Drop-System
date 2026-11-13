"""Fail-closed AliExpress TOP/OP client with supervised durable afterpay.

References: https://ds.aliexpress.com/dropshipping-api and Open Platform
method reference. TOP signs sorted pairs; OP also prefixes the API path.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import time

import requests
from dotenv import dotenv_values
from src.api.credential_file import credential_lock, merge_credentials_locked


class AliExpressAPIError(RuntimeError):
    """Safe diagnostic without raw payloads, URLs or credentials."""


class AliExpressCapabilityError(AliExpressAPIError):
    """The authorized application cannot safely perform this operation."""


class AliExpressAPIClient:
    # TOP methods that are documented READ-ONLY (no side effects): safe to retry on
    # transport errors/5xx because an identical request always yields an identical
    # result. Allowlist-by-design (fail safe): any method NOT listed here is treated
    # as potentially mutating and only retries on 429, never on 5xx. See Hata 13/22.
    _IDEMPOTENT_METHODS = frozenset({
        'aliexpress.ds.text.search',
        'aliexpress.ds.product.get',
        'aliexpress.ds.freight.query',
        'aliexpress.ds.product.specialinfo.get',
        'aliexpress.ds.product.wholesale.get',
        'aliexpress.ds.member.benefit.get',
        'aliexpress.ds.category.get',
        'aliexpress.ds.category.tree.get',
        'aliexpress.ds.image.searchV2',
        'aliexpress.ds.feed.itemids.get',
        'aliexpress.logistics.buyer.freight.calculate',
        'aliexpress.product.eancode.info.query',
        'aliexpress.affiliate.product.query',
        'aliexpress.affiliate.productdetail.get',
        'aliexpress.trade.ds.order.get',
        'aliexpress.ds.order.tracking.get',
        'aliexpress.photobank.redefining.listimagepagination',
    })

    def __init__(self, config_path=None, session=None):
        self.config_path = Path(config_path or Path(__file__).resolve().parents[2] / '.env').resolve()
        self.metadata_path = self.config_path.parent / 'data' / 'aliexpress_oauth_metadata.json'
        self.session = session if session is not None else requests.Session()
        self.base_url = 'https://api-sg.aliexpress.com'
        self._reload()

    def _reload(self):
        self.config = dict(dotenv_values(self.config_path))
        for name in ('app_key', 'app_secret', 'access_token', 'refresh_token', 'seller_id'):
            setattr(self, name, self.config.get('ALIEXPRESS_' + name.upper()))

    def _generate_sign(self, params, timestamp=None, path=''):
        text = path + ''.join(str(k) + str(params[k]) for k in sorted(params) if k != 'sign')
        return hmac.new(self.app_secret.encode(), text.encode(), hashlib.sha256).hexdigest().upper()

    @staticmethod
    def _check_errors(value, method):
        if isinstance(value, dict):
            if (method == 'aliexpress.ds.product.specialinfo.get'
                    and value.get('code') == 'APPKEY_NOT_ALLOWED'):
                raise AliExpressCapabilityError(method + ': APPKEY_NOT_ALLOWED')
            if 'error_response' in value:
                error = value['error_response']
                code = str(error.get('sub_code') or error.get('code') or 'business-error')
                # Do not echo arbitrary server text; allow only short machine codes.
                known = {'InsufficientPermission', 'InvalidApiPath', 'InvalidMethod',
                         'isp.service-not-exist', 'isp.service-unavailable', 'IncompleteSignature',
                         'InvalidSignature', 'IllegalAccessToken', 'isv.invalid-parameter',
                         'InvalidAppKey', 'InvalidTimestamp', 'InvalidAccessToken'}
                safe = code if code in known or (code.isascii() and code.isdigit() and len(code) <= 10) else 'business-error'
                cls = AliExpressCapabilityError if safe in ('InsufficientPermission', 'InvalidApiPath', 'InvalidMethod', 'isp.service-not-exist') else AliExpressAPIError
                raise cls(method + ': ' + safe)
            if any(str(value.get(key, '')).lower() == 'false' for key in ('success', 'is_success')):
                raise AliExpressAPIError(method + ': business success=false')
            for key in ('code', 'rsp_code', 'resp_code', 'error_code'):
                if (key == 'code' and method == 'aliexpress.ds.product.specialinfo.get'
                        and value.get('ret') in (True, 'true') and value.get(key) == 'null'):
                    continue  # Documented successful specialinfo result, not a global null-code rule.
                if (key == 'error_code' and method == 'aliexpress.product.eancode.info.query'
                        and (value.get('success') is True or value.get('success') == 'true')
                        and value.get(key) == 'null'):
                    continue  # Narrow documented no-error marker, not a global null allowance.
                if key in value and value[key] is not None and str(value[key]) not in ('0', '00', '200', ''):
                    raise AliExpressAPIError(method + ': business error (' + key + ')')
            for nested_key, nested in value.items():
                # Freight option `code` is a logistics service ID, not status.
                # The dedicated freight parser validates this subtree strictly.
                if method == 'aliexpress.ds.freight.query' and nested_key == 'delivery_options':
                    continue
                if method == 'aliexpress.ds.member.benefit.get' and nested_key in ('result', 'benefit_catalog') and isinstance(nested, list):
                    # Benefit code (e.g. auto-pay) is an identifier, not status.
                    for row in nested:
                        if not isinstance(row, dict):
                            raise AliExpressAPIError(method + ': malformed benefit record')
                        AliExpressAPIClient._check_errors({k: v for k, v in row.items() if k != 'code'}, method)
                    continue
                if isinstance(nested, (dict, list)):
                    AliExpressAPIClient._check_errors(nested, method)
        elif isinstance(value, list):
            for nested in value:
                AliExpressAPIClient._check_errors(nested, method)

    @staticmethod
    def _validate_search_event(report_text):
        """Deliberately narrow documented EXP schema; no identifiers or PII."""
        import re
        if (not isinstance(report_text, str)
                or not re.fullmatch(r'time=[1-9][0-9]{12}&event=EXP', report_text)
                or report_text == 'time=1640966400123&event=EXP'):
            raise ValueError('Only an actual time=<13 digit milliseconds>&event=EXP event is supported')
        return report_text

    def report_search_event(self, report_text, *, dry_run=False):
        """Explicit external telemetry WRITE, never scheduled or auto-retried.

        Send only real consented events. A response is not independent readback:
        the API documents no event lookup. Unknown outcomes require review.
        """
        if type(dry_run) is not bool:
            raise ValueError('dry_run must be boolean')
        text = self._validate_search_event(report_text)
        if dry_run:
            return {'method':'aliexpress.ds.search.event.report',
                    'params':{'report_text':text}, 'submitted':False, 'state_verified':False}
        result = self._request('aliexpress.ds.search.event.report', {'report_text':text})
        if str(result.get('code')) != '0' or not isinstance(result.get('data'), str):
            raise AliExpressAPIError('Search event: unsupported acknowledgement; do not retry automatically')
        return {'submitted':True, 'acknowledged':True, 'state_verified':False}

    def list_photobank_images(self, *, group_id='0', current_page=1,
                              page_size=20, location_type='0'):
        """Read one bounded photobank page; never delete or infer all pages.

        Page size 1..50 is a local safety bound, not a claimed provider maximum.
        Only the documented location_type example '0' is currently supported.
        """
        if (type(current_page) is not int or current_page < 1
                or type(page_size) is not int or not 1 <= page_size <= 50):
            raise ValueError('Use a positive page number and page size 1..50')
        if not isinstance(group_id, str) or not group_id.isascii() or not group_id.isdigit():
            raise ValueError('Exact numeric group ID string required')
        if location_type != '0' or not isinstance(location_type, str):
            raise ValueError('Only location_type string 0 is supported')
        body = {'group_id': group_id, 'current_page': str(current_page),
                'location_type': location_type, 'page_size': str(page_size)}
        envelope = self._request('aliexpress.photobank.redefining.listimagepagination', {
            'aeop_image_pagination_request': json.dumps(body, separators=(',', ':'))})
        result = envelope.get('result')
        if not isinstance(result, dict) or not (result.get('success') is True or result.get('success') == 'true'):
            raise AliExpressAPIError('Photobank pagination: unsuccessful or unsupported response')
        rows = result.get('images')
        total = self._number(result.get('total'), integer=True)
        pages = self._number(result.get('total_page'), integer=True)
        if (not isinstance(rows, list) or total is None or pages is None
                or len(rows) > page_size or total < len(rows)
                or (total > 0 and pages < 1)):
            raise AliExpressAPIError('Photobank pagination: invalid page or totals')
        identities = []
        for row in rows:
            if not isinstance(row, dict):
                raise AliExpressAPIError('Photobank pagination: invalid image record')
            identities.append(self._product_id(row.get('iid')))
        if len(identities) != len(set(identities)):
            raise AliExpressAPIError('Photobank pagination: duplicate image identity')
        query = result.get('query')
        if query is not None:
            if not isinstance(query, dict) or any(
                    key in query and str(query[key]) != body[key] for key in body):
                raise AliExpressAPIError('Photobank pagination: returned query mismatch')
        return {'images': rows, 'total': total, 'total_page': pages,
                'current_page': current_page, 'page_size': page_size,
                'all_pages_fetched': current_page == 1 and pages <= 1 and total == len(rows)}

    @staticmethod
    def _validate_photo_delete(params):
        if not isinstance(params, dict) or set(params) != {'aeop_delete_image_request'}:
            raise ValueError('Exactly one scoped photo deletion request is required')
        try:
            raw = params['aeop_delete_image_request']
            body = json.loads(raw) if isinstance(raw, str) else None
        except (ValueError, TypeError):
            raise ValueError('Photo deletion requires valid JSON') from None
        if not isinstance(body, dict) or set(body) != {'image_repository_id'}:
            raise ValueError('A single explicit photo repository ID is required')
        image_id = body['image_repository_id']
        if not isinstance(image_id, str):
            raise ValueError('Exact numeric photo repository ID string required')
        return AliExpressAPIClient._product_id(image_id)

    def delete_unused_photo(self, image_repository_id, *, dry_run=True,
                            confirmed_image_repository_id=None):
        """Prepare by default; live deletion requires opt-in AND exact ID scope.

        A successful acknowledgement is not independent proof of deletion.
        Never retry automatically after an ambiguous result or transport failure.
        """
        if type(dry_run) is not bool:
            raise ValueError('dry_run must be boolean')
        params = {'aeop_delete_image_request': json.dumps(
            {'image_repository_id': image_repository_id}, separators=(',', ':'))}
        image_id = self._validate_photo_delete(params)
        method = 'aliexpress.photobank.redefining.delunusephoto'
        if dry_run:
            return {'method': method, 'params': params, 'submitted': False,
                    'deletion_verified': False}
        if not isinstance(confirmed_image_repository_id, str) or confirmed_image_repository_id != image_id:
            raise AliExpressCapabilityError('Photo deletion requires explicit confirmation of the exact image ID')
        result = self._request(method, params).get('result')
        if not isinstance(result, dict) or not (result.get('is_success') is True or result.get('is_success') == 'true'):
            raise AliExpressAPIError('Photo deletion outcome unconfirmed; reconcile before retrying')
        return {'submitted': True, 'acknowledged': True, 'deletion_verified': False,
                'image_repository_id': image_id}

    @staticmethod
    def _validate_photo_upload(params, files, *, _allow_gif=False):
        """Validate actual bounded image bytes, not paths, source code or URLs."""
        from io import BytesIO
        from PIL import Image, UnidentifiedImageError
        if not isinstance(params, dict) or set(params) - {'group_id', 'file_name'} or not params.get('file_name'):
            raise ValueError('Explicit safe image filename required')
        name = params['file_name']
        if (not isinstance(name, str) or len(name) > 256 or name != name.strip()
                or any(char in name for char in '/\\:') or any(ord(char) < 32 for char in name)):
            raise ValueError('Image filename must be a bounded basename')
        group = params.get('group_id')
        if group is not None and (not isinstance(group, str) or not group.isascii() or not group.isdigit()):
            raise ValueError('Exact numeric group ID string required')
        if not isinstance(files, dict) or set(files) != {'image_bytes'}:
            raise ValueError('Exactly one image file is required')
        item = files['image_bytes']
        if not isinstance(item, tuple) or len(item) != 3 or item[0] != name:
            raise ValueError('Image multipart filename mismatch')
        content = item[1]
        if not isinstance(content, bytes) or not 0 < len(content) <= 3_000_000:
            raise ValueError('Image must contain 1..3000000 bytes')
        try:
            with Image.open(BytesIO(content)) as image:
                width, height, fmt = image.width, image.height, image.format
                if not 0 < width <= 5000 or not 0 < height <= 5000:
                    raise ValueError('Image dimensions exceed 5000x5000')
                image.verify()
            # JPEG/GIF verify() alone may not decode pixels or detect truncation.
            with Image.open(BytesIO(content)) as decoded:
                decoded.load()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
            raise ValueError('The file is not a valid supported image') from None
        kinds = {'PNG': ('image/png', {'.png'}), 'JPEG': ('image/jpeg', {'.jpg', '.jpeg'})}
        if _allow_gif:
            kinds['GIF'] = ('image/gif', {'.gif'})
        if fmt not in kinds or item[2] != kinds[fmt][0] or Path(name).suffix.lower() not in kinds[fmt][1]:
            raise ValueError('Unsupported or mismatched image data, extension and MIME')
        return {'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content),
                'width': width, 'height': height, 'mime': item[2]}

    def upload_image(self, image_path, *, group_id='0', file_name=None, dry_run=True,
                     confirmed_sha256=None):
        """Preview by default; upload exact consented PNG/JPEG bytes only.

        No automatic retries. A returned URL is an acknowledgement, not verified
        remote persistence. Never upload Python files or sample SDK paths.
        """
        if type(dry_run) is not bool:
            raise ValueError('dry_run must be boolean')
        path = Path(image_path)
        if path.suffix.lower() not in {'.png', '.jpg', '.jpeg'}:
            raise ValueError('A real PNG/JPEG image file is required')
        name = path.name if file_name is None else file_name
        with path.open('rb') as handle:
            content = handle.read(3_000_001)
        mime = 'image/png' if path.suffix.lower() == '.png' else 'image/jpeg'
        params = {'file_name': name}
        if group_id is not None:
            params['group_id'] = group_id
        files = {'image_bytes': (name, content, mime)}
        metadata = self._validate_photo_upload(params, files)
        method = 'aliexpress.photobank.redefining.uploadimageforsdk'
        if dry_run:
            return dict(metadata, method=method, file_name=name, submitted=False, upload_verified=False)
        if not isinstance(confirmed_sha256, str) or confirmed_sha256 != metadata['sha256']:
            raise AliExpressCapabilityError('Image upload requires confirmation of the exact image hash')
        result = self._request(method, params, files=files).get('result')
        from urllib.parse import urlparse
        url = result.get('photobank_url') if isinstance(result, dict) else None
        parsed = urlparse(url) if isinstance(url, str) else None
        if (not isinstance(result, dict) or not (result.get('is_success') is True or result.get('is_success') == 'true')
                or parsed is None or parsed.scheme not in ('https', 'http') or not parsed.hostname
                or not any(parsed.hostname == host or parsed.hostname.endswith('.' + host)
                           for host in ('alicdn.com', 'aliexpress-media.com'))):
            raise AliExpressAPIError('Photo upload outcome unconfirmed; reconcile before retrying')
        return dict(metadata, submitted=True, acknowledged=True, upload_verified=False, photobank_url=url)

    @staticmethod
    def _validate_temp_upload(params, files):
        if not isinstance(params, dict) or set(params) != {'src_file_name'}:
            raise ValueError('Exactly one original image filename is required')
        if not isinstance(files, dict) or set(files) != {'file_data'}:
            raise ValueError('Exactly one temporary image multipart file is required')
        name = params['src_file_name']
        if not isinstance(name, str) or Path(name).suffix.lower() not in {'.jpg', '.jpeg', '.gif'}:
            raise ValueError('Temporary upload requires JPEG/GIF image data')
        return AliExpressAPIClient._validate_photo_upload(
            {'file_name': name}, {'image_bytes': files['file_data']}, _allow_gif=True)

    def upload_temp_image(self, image_path, *, src_file_name=None, dry_run=True,
                          confirmed_sha256=None):
        """Upload a consented temporary image; default is local preview only.

        Local conservative bounds are 3 MB and 5000x5000; no PDF upload is
        enabled because the official parameter description is ambiguous.
        A remote URL is not independent persistence or lifetime verification.
        """
        if type(dry_run) is not bool:
            raise ValueError('dry_run must be boolean')
        path = Path(image_path)
        if path.suffix.lower() not in {'.jpg', '.jpeg', '.gif'}:
            raise ValueError('A real JPEG/GIF image file is required')
        name = path.name if src_file_name is None else src_file_name
        with path.open('rb') as handle:
            content = handle.read(3_000_001)
        params = {'src_file_name': name}
        mime = 'image/gif' if path.suffix.lower() == '.gif' else 'image/jpeg'
        files = {'file_data': (name, content, mime)}
        metadata = self._validate_temp_upload(params, files)
        method = 'aliexpress.image.redefining.uploadtempimageforsdk'
        if dry_run:
            return dict(metadata, method=method, src_file_name=name, submitted=False, upload_verified=False)
        if not isinstance(confirmed_sha256, str) or confirmed_sha256 != metadata['sha256']:
            raise AliExpressCapabilityError('Temporary upload requires exact image hash confirmation')
        result = self._request(method, params, files=files).get('result')
        from urllib.parse import urlparse
        url = result.get('url') if isinstance(result, dict) else None
        parsed = urlparse(url) if isinstance(url, str) else None
        if (not isinstance(result, dict) or not (result.get('is_success') is True or result.get('is_success') == 'true')
                or parsed is None or parsed.scheme not in ('https', 'http') or not parsed.hostname
                or not any(parsed.hostname == host or parsed.hostname.endswith('.' + host)
                           for host in ('alicdn.com', 'aliexpress-media.com'))):
            raise AliExpressAPIError('Temporary upload outcome unconfirmed; reconcile before retrying')
        return dict(metadata, submitted=True, acknowledged=True, upload_verified=False, url=url)

    def _request(self, method, params=None, op=False, files=None, *, payment_authorization=None):
        self._reload()
        if method == 'aliexpress.photobank.redefining.uploadimageforsdk':
            from src.runtime import writes_allowed
            if (op or not writes_allowed(self.config)
                    or str(self.config.get('ALLOW_PHOTOBANK_UPLOADS', '')).lower() != 'true'):
                raise AliExpressCapabilityError('Image upload disabled by write protection or explicit upload consent')
            metadata = self._validate_photo_upload(params, files)
            if self.config.get('PHOTOBANK_UPLOAD_SHA256') != metadata['sha256']:
                raise AliExpressCapabilityError('Image upload is not authorized for these exact image bytes')
        elif method == 'aliexpress.image.redefining.uploadtempimageforsdk':
            from src.runtime import writes_allowed
            if (op or not writes_allowed(self.config)
                    or str(self.config.get('ALLOW_TEMP_IMAGE_UPLOADS', '')).lower() != 'true'):
                raise AliExpressCapabilityError('Temporary upload disabled by write protection or explicit consent')
            metadata = self._validate_temp_upload(params, files)
            if self.config.get('TEMP_IMAGE_UPLOAD_SHA256') != metadata['sha256']:
                raise AliExpressCapabilityError('Temporary upload is not authorized for these exact image bytes')
        elif files is not None:
            raise AliExpressCapabilityError('Multipart files require a guarded image upload adapter')
        if method == 'aliexpress.photobank.redefining.delunusephoto':
            from src.runtime import writes_allowed
            image_id = self._validate_photo_delete(params)
            if (op or not writes_allowed(self.config)
                    or str(self.config.get('ALLOW_PHOTOBANK_DELETIONS', '')).lower() != 'true'
                    or self.config.get('PHOTOBANK_DELETE_IMAGE_ID') != image_id):
                raise AliExpressCapabilityError('Photo deletion disabled by write protection or exact image authorization')
        if method == 'aliexpress.ds.order.afterpay':
            if op:
                raise AliExpressCapabilityError('Afterpay requires the documented TOP transport')
            from src.payment_executor import consume_transport_authorization
            consume_transport_authorization(self, params, payment_authorization)
        if method == 'aliexpress.ds.search.event.report':
            from src.runtime import writes_allowed
            if (op or not writes_allowed(self.config)
                    or str(self.config.get('ALLOW_SEARCH_EVENT_REPORTING', '')).lower() != 'true'):
                raise AliExpressCapabilityError('Search event reporting disabled by write protection or telemetry consent')
            if not isinstance(params, dict) or set(params) != {'report_text'}:
                raise ValueError('Only report_text is supported for event reporting')
            self._validate_search_event(params['report_text'])
        if not self.app_key or not self.app_secret or (not op and not self.access_token):
            raise AliExpressCapabilityError('AliExpress credentials missing from configured file')
        data = {'app_key': self.app_key, 'timestamp': str(int(time.time() * 1000)), 'sign_method': 'sha256'}
        if not op:
            data.update(method=method, session=self.access_token, format='json', v='2.0')
        data.update({k: str(v) for k, v in (params or {}).items() if v is not None})
        data['sign'] = self._generate_sign(data, path=method if op else '')
        url = self.base_url + ('/rest' + method if op else '/sync')
        # All TOP calls are HTTP POST regardless of read/write semantics, so (unlike the
        # eBay client) idempotency can't be inferred from the HTTP verb. Classify by TOP
        # method name instead: only documented READ-ONLY methods (no side effects, same
        # request -> same result) retry on transport errors/5xx. Anything else (order
        # creation, afterpay, uploads, deletes, event reporting) is potentially mutating,
        # so a 5xx is ambiguous (may have already executed server-side) and is never
        # blind-retried -- only 429 (rate-limited BEFORE the server did anything) is safe
        # for those, mirroring src/api/ebay_client.py:_request()'s GET/PUT vs POST/DELETE split.
        idempotent = method in self._IDEMPOTENT_METHODS
        retries = 0
        MAX_RETRIES = 3
        while True:
            try:
                if files is None:
                    response = self.session.post(url, data=data, timeout=30)
                else:
                    # TOP signs text fields; binary bytes travel as a multipart file.
                    response = self.session.post(url, data=data, files=files, timeout=30)
            except requests.RequestException:
                if idempotent and retries < MAX_RETRIES:
                    retries += 1
                    time.sleep(min(0.5 * 2 ** retries, 8.0))
                    continue
                raise AliExpressAPIError(method + ': transport failure') from None
            retryable = response.status_code == 429 or (idempotent and 500 <= response.status_code < 600)
            if retryable and retries < MAX_RETRIES:
                retries += 1
                time.sleep(min(0.5 * 2 ** retries, 8.0))
                continue
            break
        if not 200 <= response.status_code < 300:
            raise AliExpressAPIError(method + ': HTTP ' + str(response.status_code))
        try:
            payload = response.json()
        except (ValueError, TypeError):
            raise AliExpressAPIError(method + ': invalid JSON') from None
        if not isinstance(payload, dict):
            raise AliExpressAPIError(method + ': unsupported response schema')
        self._check_errors(payload, method)
        if op:
            return payload
        key = method.replace('.', '_') + '_response'
        if key not in payload or not isinstance(payload[key], dict):
            raise AliExpressAPIError(method + ': missing response envelope')
        return payload[key]

    @staticmethod
    def _number(value, integer=False):
        try:
            from decimal import Decimal
            n = Decimal(str(value))
            if not n.is_finite() or n < 0 or (integer and n != n.to_integral_value()):
                return None
            if integer:
                return int(n)
            import math
            value = float(n)
            return value if math.isfinite(value) else None
        except (ValueError, TypeError, ArithmeticError):
            return None

    @staticmethod
    def _product_id(value):
        text = str(value)
        if not text.isascii() or not text.isdigit() or int(text) <= 0:
            raise AliExpressCapabilityError('A real numeric AliExpress product ID is required')
        return text

    @staticmethod
    def _atomic_write(path, text):
        import tempfile
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=path.name + '.', dir=str(path.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def refresh_access_token(self, force=False):
        """Refresh only when due (or explicitly forced); persist no secret metadata.

        A shared .env.lock directory serializes cooperating writers. Always merge
        the latest file, not the constructor's cached configuration.
        """
        try:
            return self._refresh_access_token_locked(force)
        except (OSError, ValueError, TypeError, OverflowError, AttributeError):
            raise AliExpressAPIError('AliExpress renewal or credential persistence failed') from None

    def _refresh_access_token_locked(self, force):
        with credential_lock(self.config_path):
            self._reload()
            try:
                metadata = json.loads(self.metadata_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                metadata = {}
            if not isinstance(metadata, dict):
                metadata = {}
            expiry = self._number(metadata.get('expires_at')) if isinstance(metadata, dict) else None
            token_hash = hashlib.sha256((self.access_token or '').encode()).hexdigest()
            if (not force and expiry is not None and expiry > time.time() + 300
                    and self.access_token and metadata.get('token_sha256') == token_hash):
                return True
            if not self.refresh_token:
                raise AliExpressCapabilityError('AliExpress refresh token missing')
            result = self._request('/auth/token/refresh', {'refresh_token':self.refresh_token}, op=True)
            if not isinstance(result.get('access_token'), str) or not result['access_token']:
                raise AliExpressAPIError('AliExpress refresh: no access token in response')
            expires = self._number(result.get('expires_in'))
            if expires is None or expires <= 0:
                raise AliExpressAPIError('AliExpress refresh: missing expiry')
            updates = {'ALIEXPRESS_ACCESS_TOKEN':result['access_token']}
            if result.get('refresh_token'):
                updates['ALIEXPRESS_REFRESH_TOKEN'] = result['refresh_token']
            # Newline injection is never a valid credential.
            if any('\n' in str(v) or '\r' in str(v) for v in updates.values()):
                raise AliExpressAPIError('AliExpress refresh: malformed credential')
            refresh_expiry = self._number(result.get('refresh_expires_in', 0))
            if refresh_expiry is None:
                raise AliExpressAPIError('AliExpress refresh: malformed refresh expiry')
            renewal_count = self._number(metadata.get('renewal_count', 0), integer=True) or 0
            merge_credentials_locked(self.config_path, updates)
            now = time.time()
            safe_metadata = {'updated_at':now, 'expires_at':now+expires,
                             'token_sha256':hashlib.sha256(result['access_token'].encode()).hexdigest(),
                             'refresh_expires_at':now+refresh_expiry,
                             'renewal_count':renewal_count+1}
            self._atomic_write(self.metadata_path, json.dumps(safe_metadata, indent=2))
            self._reload()
            return True

    def pay_order(self, order_id, *, ebay_order_id, ebay_line_item_id,
                  approval_path=None, dry_run=True):
        """Execute only through the durable supervised executor; preview by default.

        ALLOW_ORDER_PAYMENTS is separate from purchase and runtime write gates.
        The executor binds the known supplier ID to the persisted eBay line,
        fresh EUR checkout total, SKU/quantity, cap and expiring approval.
        """
        from src.payment_executor import PaymentExecutor
        return PaymentExecutor(self).pay_order(order_id, ebay_order_id=ebay_order_id,
            ebay_line_item_id=ebay_line_item_id, approval_path=approval_path, dry_run=dry_run)

    def prepare_order_afterpay(self, order_id):
        """Build the documented contract locally; this helper NEVER executes.

        Use pay_order for actual scoped execution and durable reconciliation.
        live_execution_supported=False describes this preparation-only helper,
        not platform/account capability. No payment or saved card is assumed.
        """
        if not isinstance(order_id, str):
            raise ValueError('An exact numeric supplier order ID string is required')
        order_id = self._product_id(order_id)
        return {'method': 'aliexpress.ds.order.afterpay',
                'params': {'req': json.dumps({'order_id': order_id}, separators=(',', ':'))},
                'submitted': False, 'payment_verified': False,
                'live_execution_supported': False, 'request_contract_verified': True,
                'execution_entrypoint': 'pay_order',
                'blocker_scope': 'local_preview_has_no_payment_readback',
                'blockers': ['payment_success_contract_unverified',
                             'scoped_payment_authorization_required',
                             'fresh_bound_checkout_read_required',
                             'durable_single_use_claim_required']}

    def get_order(self, order_id):
        order_id = self._product_id(order_id)
        envelope = self._request('aliexpress.trade.ds.order.get', {
            'single_order_query':json.dumps({'order_id':int(order_id)}, separators=(',', ':'))})
        result = envelope.get('result')
        if not isinstance(result, dict) or not result.get('order_status'):
            raise AliExpressAPIError('aliexpress.trade.ds.order.get: unsupported or empty order schema')
        returned_id = result.get('order_id', result.get('id'))
        if returned_id is not None and str(returned_id) != order_id:
            raise AliExpressAPIError('aliexpress.trade.ds.order.get: mismatched order ID')
        return dict(result, order_id=order_id)

    def get_orders(self, status='PLACE_ORDER_SUCCESS', start_time=None, end_time=None):
        # DS exposes lookup by known order ID; a seller order-list or affiliate
        # commission list is NOT the authorized buyer's purchased-order list.
        raise AliExpressCapabilityError('DS buyer order-list API is not verified; use get_order(order_id) for persisted supplier IDs')

    def get_order_tracking(self, order_id, language='en_US'):
        """Read supplier tracking only; never upload to eBay or mark fulfillment.

        A response is not proof of paid/dispatched state or item-line ownership.
        The existing fulfillment reconciliation must still verify those separately.
        """
        import re
        if not isinstance(order_id, str):
            raise ValueError('Exact supplier order ID string required')
        order_id = self._product_id(order_id)
        if not isinstance(language, str) or not re.fullmatch(r'[a-z]{2}_[A-Z]{2}', language):
            raise ValueError('Tracking language requires a locale such as en_US')
        envelope = self._request('aliexpress.ds.order.tracking.get', {
            'ae_order_id': order_id, 'language': language})
        result = envelope.get('result')
        if not isinstance(result, dict) or not (result.get('ret') is True or result.get('ret') == 'true'):
            raise AliExpressAPIError('aliexpress.ds.order.tracking.get: no successful tracking response')
        data = result.get('data')
        rows = data.get('tracking_detail_line_list') if isinstance(data, dict) else None
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise AliExpressAPIError('aliexpress.ds.order.tracking.get: unsupported tracking schema')
        return result

    def get_feed_item_ids(self, feed_name, page_size=None, category_id=None, search_id=None):
        """Fetch one feed page; total is provider's remaining count, not a sum.

        Cursor is returned unchanged. Never implies product approval or stock.
        """
        if not isinstance(feed_name, str) or not feed_name.strip() or len(feed_name) > 200:
            raise ValueError('A real feed name is required')
        params = {'feed_name': feed_name}
        if page_size is not None:
            if type(page_size) is not int or not 1 <= page_size <= 200:
                raise ValueError('Feed page size must be an integer between 1 and 200')
            params['page_size'] = page_size
        if category_id is not None:
            params['category_id'] = self._product_id(category_id)
        if search_id is not None:
            if (not isinstance(search_id, str) or not search_id.strip() or len(search_id) > 4096
                    or search_id == 'abc123' or any(ord(c) < 32 for c in search_id)):
                raise ValueError('Use the actual returned cursor, or omit for the first page')
            params['search_id'] = search_id
        envelope = self._request('aliexpress.ds.feed.itemids.get', params)
        result = envelope.get('result')
        if envelope.get('ret') not in (True, 'true') or not isinstance(result, dict):
            raise AliExpressAPIError('Feed: unsuccessful or unsupported page')
        total = self._number(result.get('total'), integer=True)
        products = result.get('products')
        if total == 0 and products == {}:
            products = []  # Verified live empty encoding; not a general fallback.
        if total is None or not isinstance(products, list):
            raise AliExpressAPIError('Feed: malformed count or products')
        ids = [self._product_id(value) for value in products]
        cursor = result.get('search_id')
        if cursor is not None and (not isinstance(cursor, str) or not cursor):
            raise AliExpressAPIError('Feed: malformed cursor')
        return dict(result, total=total, products=ids)

    def get_member_benefits(self):
        """Query member benefits; eligibility never grants purchase permission."""
        payload = self._request('aliexpress.ds.member.benefit.get')
        rows = payload.get('result')
        if isinstance(rows, dict):
            rows = rows.get('benefit_catalog')
        if not isinstance(rows, list):
            raise AliExpressAPIError('aliexpress.ds.member.benefit.get: unsupported benefit list')
        normalized = []
        for row in rows:
            if (not isinstance(row, dict) or not isinstance(row.get('code'), str)
                    or not row['code'] or ('title' in row and not isinstance(row['title'], str))):
                raise AliExpressAPIError('aliexpress.ds.member.benefit.get: invalid benefit record')
            record = {'code': row['code']}
            if 'title' in row:
                record['title'] = row['title']
            for field in ('canApply', 'canBenefit'):
                value = row.get(field)
                if type(value) is bool:
                    record[field] = value
                elif isinstance(value, str) and value in ('true', 'false'):
                    record[field] = value == 'true'
                else:
                    raise AliExpressAPIError('aliexpress.ds.member.benefit.get: invalid eligibility flag')
            normalized.append(record)
        return normalized

    @staticmethod
    def _affiliate_products(payload) -> dict:
        envelope = payload.get('resp_result') if isinstance(payload, dict) else None
        result = envelope.get('result') if isinstance(envelope, dict) else None
        if (not isinstance(envelope, dict) or envelope.get('resp_code') not in (200, '200')
                or not isinstance(result, dict)):
            raise AliExpressAPIError('Affiliate products: unsupported response')
        rows = result.get('products')
        if isinstance(rows, dict) and set(rows) == {'product'}:
            rows = rows['product']
        count = AliExpressAPIClient._number(result.get('current_record_count'), integer=True)
        if not isinstance(rows, list) or count is None or count != len(rows):
            raise AliExpressAPIError('Affiliate products: invalid product list or count')
        ids = []
        for row in rows:
            if not isinstance(row, dict):
                raise AliExpressAPIError('Affiliate products: malformed product')
            ids.append(AliExpressAPIClient._product_id(row.get('product_id')))
        if len(ids) != len(set(ids)):
            raise AliExpressAPIError('Affiliate products: duplicate product identity')
        return dict(result, products=rows, discovery_only=True, inventory_verified=False, ready_to_publish=False)

    def query_affiliate_products(self, keywords, *, page_no=1, page_size=20,
                                 category_ids=None, sort='SALE_PRICE_ASC'):
        """Optional alternative discovery; never a DS stock/freight fallback."""
        if not isinstance(keywords, str) or not keywords.strip() or len(keywords) > 250:
            raise ValueError('A bounded nonempty discovery keyword is required')
        if (type(page_no) is not int or page_no < 1 or type(page_size) is not int
                or not 1 <= page_size <= 50):
            raise ValueError('Use positive page and page size 1..50')
        if sort not in ('SALE_PRICE_ASC', 'SALE_PRICE_DESC', 'LAST_VOLUME_ASC', 'LAST_VOLUME_DESC'):
            raise ValueError('Unsupported affiliate sorting')
        params = {'keywords': keywords, 'page_no': page_no, 'page_size': page_size,
                  'sort': sort, 'target_currency': 'EUR', 'target_language': 'DE', 'ship_to_country': 'DE'}
        if category_ids is not None:
            if (not isinstance(category_ids, list) or not 1 <= len(category_ids) <= 20
                    or any(not isinstance(value, str) for value in category_ids)):
                raise ValueError('Explicit bounded category ID string list required')
            params['category_ids'] = ','.join(self._product_id(value) for value in category_ids)
        result = self._affiliate_products(self._request('aliexpress.affiliate.product.query', params))
        if len(result['products']) > page_size:
            raise AliExpressAPIError('Affiliate products: oversized page')
        if 'current_page_no' in result and str(result['current_page_no']) != str(page_no):
            raise AliExpressAPIError('Affiliate products: page mismatch')
        return result

    def get_affiliate_product_details(self, product_ids):
        """Optional catalog/EAN metadata; never approves SKU stock or rights."""
        if (not isinstance(product_ids, list) or not 1 <= len(product_ids) <= 20
                or any(not isinstance(value, str) for value in product_ids)):
            raise ValueError('An explicit list of 1..20 product ID strings is required')
        ids = [self._product_id(value) for value in product_ids]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate product IDs are not allowed')
        result = self._affiliate_products(self._request('aliexpress.affiliate.productdetail.get', {
            'product_ids': ','.join(ids), 'target_currency': 'EUR', 'target_language': 'DE', 'country': 'DE'}))
        if any(str(row['product_id']) not in ids for row in result['products']):
            raise AliExpressAPIError('Affiliate details: unexpected product identity')
        returned = {str(row['product_id']) for row in result['products']}
        return dict(result, missing_product_ids=[value for value in ids if value not in returned])

    def get_ean_info(self, ean_code):
        """Read catalog metadata for an exact checksum-valid EAN-8/EAN-13.

        A matching EAN response does not establish GS1 ownership, SKU identity,
        product authenticity or permission to use another listing's content.
        """
        if (not isinstance(ean_code, str) or len(ean_code) not in (8, 13)
                or not ean_code.isascii() or not ean_code.isdigit()):
            raise ValueError('Exact EAN-8 or EAN-13 digits required')
        weighted = sum(int(digit) * (3 if i % 2 == 0 else 1)
                       for i, digit in enumerate(reversed(ean_code[:-1])))
        if (10 - weighted % 10) % 10 != int(ean_code[-1]):
            raise ValueError('EAN checksum mismatch')
        result = self._request('aliexpress.product.eancode.info.query', {'ean_code': ean_code}).get('result')
        if (not isinstance(result, dict) or not (result.get('success') is True or result.get('success') == 'true')
                or result.get('ean_code') != ean_code):
            raise AliExpressAPIError('EAN query: unsupported or mismatched response')
        return result

    def get_categories(self, category_id=None, language='de', app_signature=None):
        """Read supplier categories; optional app_signature is not TOP's sign.

        Accepts the official direct list and the verified TOP category wrapper.
        This supplier category list is not an eBay taxonomy mapping.
        """
        supported = {'hi', 'de', 'ru', 'pt', 'ko', 'in', 'en', 'it', 'fr', 'zh',
                     'es', 'iw', 'ar', 'vi', 'th', 'uk', 'ja', 'id', 'pl', 'he', 'nl', 'tr'}
        if not isinstance(language, str) or language not in supported:
            raise ValueError('Unsupported category language')
        params = {'language': language}
        if category_id is not None:
            if not isinstance(category_id, str):
                raise ValueError('Exact numeric category ID string required')
            params['categoryId'] = self._product_id(category_id)
        if app_signature is not None:
            if (not isinstance(app_signature, str) or not app_signature.strip()
                    or app_signature == 'your signature'
                    or any(ord(char) < 32 for char in app_signature)):
                raise ValueError('Real application signature required or omit it')
            params['app_signature'] = app_signature
        payload = self._request('aliexpress.ds.category.get', params)
        envelope = payload.get('resp_result')
        result = envelope.get('result') if isinstance(envelope, dict) else None
        if (not isinstance(envelope, dict) or envelope.get('resp_code') not in (200, '200')
                or not isinstance(result, dict)):
            raise AliExpressAPIError('aliexpress.ds.category.get: unsupported capability response')
        categories = result.get('categories')
        if isinstance(categories, dict):
            categories = categories.get('category')
        if not isinstance(categories, list) or any(
                not isinstance(row, dict) or not str(row.get('category_id', '')).isascii()
                or not str(row.get('category_id', '')).isdigit()
                or not isinstance(row.get('category_name'), str) for row in categories):
            raise AliExpressAPIError('aliexpress.ds.category.get: unsupported category list')
        return dict(result, categories=categories)

    def check_token_validity(self):
        """A successful signed read proves this capability, not all API scopes.

        Failures raise; a service outage is not evidence of an expired token.
        """
        envelope = self._request('aliexpress.ds.category.get', {'language':'en'})
        result = envelope.get('resp_result')
        if not isinstance(result, dict) or result.get('resp_code') not in (200, '200') or not isinstance(result.get('result'), dict):
            raise AliExpressAPIError('aliexpress.ds.category.get: unsupported capability response')
        return True

    def create_order(self, product_id, quantity, buyer_email, shipping_address,
                     sku_id=None, external_order_id=None):
        return self._create_order_impl(product_id, quantity, buyer_email, shipping_address,
            sku_id, external_order_id, ds=False)

    def create_ds_order(self, product_id, quantity, buyer_email, shipping_address,
                        sku_id=None, external_order_id=None):
        """DS create adapter, explicitly requesting no payment, Germany/EUR only.

        Caller must reserve its durable order-line ledger and scoped approval
        before calling, just as for create_order. This method is not scheduled
        and does not enable any live/purchase flags or bypass final freight checks.
        out_order_id is correlation, not proof of provider-side idempotency.
        """
        return self._create_order_impl(product_id, quantity, buyer_email, shipping_address,
            sku_id, external_order_id, ds=True)

    def _create_order_impl(self, product_id, quantity, buyer_email, shipping_address,
                           sku_id, external_order_id, ds):
        self._reload()
        failure = {'success':False, 'order_id':None}
        from src.runtime import writes_allowed
        if not writes_allowed(self.config):
            return dict(failure, error='AliExpress purchases disabled by runtime write protection or unconfirmed supplier agreement')
        if any((self.config.get(flag) or '').lower() != 'true' for flag in
               ('AUTOMATION_LIVE_WRITES', 'ALLOW_ORDER_PURCHASES', 'SUPPLIER_AGREEMENT_CONFIRMED')):
            return dict(failure, error='AliExpress purchases disabled: live-write, purchase and supplier agreement flags must be true')
        required = ('address', 'city', 'country', 'full_name', 'mobile_no', 'province', 'zip', 'phone_country')
        if not isinstance(shipping_address, dict) or any(not shipping_address.get(k) for k in required):
            return dict(failure, error='Structured AliExpress logistics address is required')
        if shipping_address['country'] != 'DE':
            return dict(failure, error='Only Germany/EUR fulfillment is supported')
        if type(quantity) is not int or quantity <= 0 or not sku_id or not external_order_id:
            return dict(failure, error='Positive quantity, explicit SKU and external order ID required')
        if ds and (not isinstance(external_order_id, str) or not external_order_id.strip()
                   or external_order_id != external_order_id.strip()
                   or any(ord(char) < 32 for char in external_order_id)):
            return dict(failure, error='Exact nonempty external order identity string required')
        try:
            product_id = self._product_id(product_id)
            product = self.get_product_details(product_id)
            matches = [sku for sku in product['skus'] if sku['sku_id'] == str(sku_id)]
            if len(matches) != 1:
                return dict(failure, error='Selected SKU does not uniquely match current supplier inventory')
            sku = matches[0]
            if not sku.get('sku_attr') or sku.get('warehouse_count') is None or sku['warehouse_count'] < quantity:
                return dict(failure, error='SKU attributes or sufficient known inventory unavailable')
            if sku.get('currency') != 'EUR' or sku.get('sale_price') is None or sku['sale_price'] <= 0:
                return dict(failure, error='Verified EUR SKU price unavailable')
            if not product.get('product_title') or not product.get('product_main_image_url'):
                return dict(failure, error='Product title/image unavailable')
            if self._number(product.get('shipping_cost')) is None or not product.get('logistics_service_name'):
                return dict(failure, error='Verified freight quote unavailable; purchase blocked pending supported shipping schema')
            # Official documented placeorder schema (apiId=35446). Never call
            # order.afterpay. order_memo is correlation only, NOT idempotency.
            body = {'logistics_address':{k:shipping_address[k] for k in required},
                    'product_items':[{'product_id':int(product_id), 'product_count':quantity,
                                      'sku_attr':sku['sku_attr'],
                                      'logistics_service_name':product['logistics_service_name'],
                                      'order_memo':str(external_order_id)}]}
            if shipping_address.get('address2'):
                body['logistics_address']['address2'] = shipping_address['address2']
            params = {'param_place_order_request4_open_api_d_t_o': json.dumps(body, separators=(',', ':'))}
            method = 'aliexpress.trade.buy.placeorder'
            if ds:
                body['out_order_id'] = str(external_order_id)
                params['param_place_order_request4_open_api_d_t_o'] = json.dumps(body, separators=(',', ':'))
                params['ds_extend_request'] = json.dumps({'payment': {
                    'try_to_pay': 'false', 'pay_currency': 'EUR'}}, separators=(',', ':'))
                method = 'aliexpress.ds.order.create'
            result = self._request(method, params).get('result')
            orders = result.get('order_list') if isinstance(result, dict) else None
            if isinstance(orders, dict):
                orders = orders.get('number')
            success = result.get('is_success') if isinstance(result, dict) else None
            accepted = success is True or (ds and success == 'true')
            if not isinstance(result, dict) or not accepted or not isinstance(orders, list) or len(orders) != 1:
                return dict(failure, error='Order outcome unknown: reconcile before retrying', uncertain=True)
            order_id = self._product_id(orders[0])
            return {'success':True, 'order_id':order_id, 'paid':False}
        except AliExpressAPIError as exc:
            # Writes are never retried automatically: a timeout may mean created.
            return dict(failure, error=str(exc), uncertain=True)

    def search_product_page(self, keyword, category_id=None, sort_by='SALES_DESC',
                            page_num=1, page_size=50, *, search_extend=None, selection_name=None):
        """One checked discovery page, not relevance, stock or compliance evidence.

        Uses the current documented camelCase wire keys. Extended filter field
        shapes are documented, but accepted searchKey vocabulary is not: only
        caller-supplied real filters are forwarded, never inferred/applied locally.
        """
        if (not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 500
                or any(ord(c) < 32 for c in keyword)
                or type(page_num) is not int or page_num < 1
                or type(page_size) is not int or not 1 <= page_size <= 50):
            raise ValueError('Invalid search query or pagination')
        sort = {'SALES_DESC':'orders,desc', 'salesDesc':'orders,desc'}.get(sort_by, sort_by)
        if sort not in {'min_price,asc', 'min_price,desc', 'orders,asc', 'orders,desc', 'comments,asc', 'comments,desc'}:
            raise ValueError('Unsupported documented sort value')
        params = {'keyWord':keyword, 'countryCode':'DE', 'currency':'EUR', 'local':'de_DE',
                  'pageIndex':page_num, 'pageSize':page_size, 'sortBy':sort}
        if category_id is not None:
            params['categoryId'] = self._product_id(category_id)
        if selection_name is not None:
            if (not isinstance(selection_name, str) or not selection_name.strip() or len(selection_name) > 200
                    or selection_name == 'selection name' or any(ord(c) < 32 for c in selection_name)):
                raise ValueError('Actual selection name required')
            params['selectionName'] = selection_name
        if search_extend is not None:
            if not isinstance(search_extend, list) or not 1 <= len(search_extend) <= 20:
                raise ValueError('Bounded list of documented extended filters required')
            for row in search_extend:
                if (not isinstance(row, dict) or not row or set(row) - {'searchKey','searchValue','min','max'}
                        or 'searchKey' not in row):
                    raise ValueError('Unsupported extended filter fields')
                for key, value in row.items():
                    if (not isinstance(value, str) or not value.strip() or len(value) > 200
                            or value in ('min','max','searchKey','searchValue')
                            or any(ord(c) < 32 for c in value)):
                        raise ValueError('Real non-placeholder extended filter strings required')
                for key in ('min','max'):
                    if key in row and self._number(row[key]) is None:
                        raise ValueError('Finite nonnegative filter bounds required')
                if 'min' in row and 'max' in row and self._number(row['min']) > self._number(row['max']):
                    raise ValueError('Filter minimum exceeds maximum')
            params['searchExtend'] = json.dumps(search_extend, separators=(',', ':'))
        result = self._request('aliexpress.ds.text.search', params)
        data = result.get('data')
        products = data.get('products') if isinstance(data, dict) else None
        rows = products.get('selection_search_product') if isinstance(products, dict) else products
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise AliExpressAPIError('aliexpress.ds.text.search: unsupported product list schema')
        for row in rows:
            self._product_id(row.get('itemId'))
        return dict(data, products=rows)

    def search_products(self, keyword, category_id=None, sort_by='SALES_DESC', page_num=1, page_size=50,
                        *, search_extend=None, selection_name=None):
        """Backward-compatible detail enrichment using the current search contract."""
        data = self.search_product_page(keyword, category_id, sort_by, page_num, page_size,
                                       search_extend=search_extend, selection_name=selection_name)
        ids = list(dict.fromkeys(self._product_id(row['itemId']) for row in data['products']))
        details = []
        for pid in ids[:page_size]:
            try:
                details.append(self.get_product_details(pid))
            except AliExpressCapabilityError:
                raise
            except AliExpressAPIError as exc:
                # A single discovered item that is offline/unavailable (business rsp_code != 200,
                # unsupported schema) must not abort the whole discovery page. Auth/signature/
                # permission failures are not per-item and keep propagating.
                text = str(exc)
                if 'business error' in text or 'business-error' in text or 'unsupported product schema' in text:
                    self._skipped_discovery = getattr(self, '_skipped_discovery', 0) + 1
                    continue
                raise
        return details

    def get_category_tree(self, lang='en_US'):
        """Read-only supplier category tree; not an eBay category mapping.

        Retains the API envelope until the provider's category schema is verified.
        """
        if lang not in {'en_US', 'de_DE'}:
            raise ValueError('Supported category languages: en_US, de_DE')
        return self._request('aliexpress.ds.category.tree.get', {'lang': lang})

    def search_products_by_image(self, image_base64):
        """Read-only V2 discovery using the supplied API contract, Germany/EUR.

        Returns the checked API envelope, not approved products or stock evidence.
        Response product fields must be verified before downstream normalization.
        """
        import base64
        import binascii
        if not isinstance(image_base64, str) or not image_base64 or len(image_base64) > 8_000_000:
            raise ValueError('A bounded base64 image string is required')
        try:
            decoded = base64.b64decode(image_base64, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError('Invalid base64 image input') from None
        if not decoded:
            raise ValueError('Image input is empty')
        params = {'sort_type': 'price', 'image_base64': image_base64,
                  'currency': 'EUR', 'lang': 'de', 'search_type': 'same',
                  'sort_order': 'asc', 'ship_to': 'DE'}
        return self._request('aliexpress.ds.image.searchV2', {
            'param0': json.dumps(params, separators=(',', ':'))})

    def get_top_products(self, category='electronics', limit=100):
        if type(limit) is not int or limit < 1:
            raise ValueError('limit must be a positive integer')
        self._reload()
        vetted = self.config.get('ALIEXPRESS_PRODUCT_IDS') or ''
        ids = list(dict.fromkeys(self._product_id(v.strip()) for v in vetted.split(',') if v.strip()))
        products, seen, page = [], set(), 1
        try:
            while len(products) < limit:
                batch = self.search_products(category, page_num=page, page_size=min(50, limit-len(products)))
                fresh = [p for p in batch if p['product_id'] not in seen]
                if not fresh:
                    break
                products.extend(fresh)
                seen.update(p['product_id'] for p in fresh)
                page += 1
            return products[:limit]
        except AliExpressCapabilityError:
            if ids:
                return [self.get_product_details(pid) for pid in ids[:limit]]
            raise AliExpressCapabilityError('DS discovery unavailable; configure vetted ALIEXPRESS_PRODUCT_IDS') from None

    def calculate_buyer_freight(self, product_id, sku_id, *, send_goods_country_code=None,
                               quantity=1, city_code=None, province_code=None):
        """Independent legacy buyer freight estimate; never a checkout/fallback.

        Caller must supply the actual dispatch country, not a seller address.
        Current explicit SKU inventory and EUR unit price are read first.
        """
        import re
        product_id, sku_id = self._product_id(product_id), self._product_id(sku_id)
        if not isinstance(send_goods_country_code, str) or not re.fullmatch(r'[A-Z]{2}', send_goods_country_code):
            raise ValueError('Actual ship-from country is required; no origin is assumed')
        if type(quantity) is not int or quantity < 1:
            raise ValueError('Positive integer quantity required')
        geo = self._geographic_codes(province_code, city_code)
        product = self.get_product_details(product_id)
        matches = [sku for sku in product['skus'] if sku['sku_id'] == sku_id]
        if len(matches) != 1:
            raise AliExpressCapabilityError('Buyer freight: SKU must uniquely match the current product')
        sku = matches[0]
        stock = self._number(sku.get('warehouse_count'), integer=True)
        price = self._number(sku.get('sale_price'))
        if stock is None or stock < quantity or price is None or price <= 0 or sku.get('currency') != 'EUR':
            raise AliExpressCapabilityError('Buyer freight: sufficient known stock and EUR price required')
        body = dict(geo, country_code='DE', product_id=product_id, sku_id=sku_id,
                    product_num=quantity, price=str(price), price_currency='EUR',
                    send_goods_country_code=send_goods_country_code)
        envelope = self._request('aliexpress.logistics.buyer.freight.calculate', {
            'param_aeop_freight_calculate_for_buyer_d_t_o':json.dumps(body, separators=(',', ':'))})
        result = envelope.get('result')
        if not isinstance(result, dict) or result.get('success') not in (True, 'true'):
            raise AliExpressAPIError('Buyer freight: unsuccessful response')
        options = result.get('aeop_freight_calculate_result_for_buyer_d_t_o_list')
        if isinstance(options, dict):
            options = options.get('aeop_freight_calculate_result_for_buyer_d_t_o')
        if not isinstance(options, list) or not options:
            raise AliExpressAPIError('Buyer freight: unsupported or empty options')
        checked = []
        for option in options:
            if not isinstance(option, dict):
                raise AliExpressAPIError('Buyer freight: malformed option')
            freight = option.get('freight')
            cost = self._number(freight.get('amount')) if isinstance(freight, dict) else None
            if (cost is None or freight.get('currency_code') != 'EUR'
                    or str(option.get('error_code')) != '0'
                    or not isinstance(option.get('service_name'), str) or not option['service_name']
                    or not isinstance(option.get('estimated_delivery_time'), str)
                    or option.get('tracking_available') not in (True, False, 'true', 'false')):
                raise AliExpressAPIError('Buyer freight: invalid amount, currency or service schema')
            checked.append(dict(option, cost=cost, currency='EUR',
                                tracking_available=option['tracking_available'] in (True, 'true')))
        return {'product_id':product_id, 'sku_id':sku_id, 'quantity':quantity,
                'ship_to_country':'DE', 'send_goods_country_code':send_goods_country_code,
                'options':checked, 'is_estimate':True, 'transaction_ready':False}

    @staticmethod
    def _geographic_codes(province_code, city_code):
        """Preserve supplied provider codes; never map cities or fix placeholders."""
        if (province_code is None) != (city_code is None):
            raise ValueError('Paired actual province_code and city_code required')
        result = {}
        for key, value in (('province_code', province_code), ('city_code', city_code)):
            if value is not None:
                if (not isinstance(value, str) or not value.strip() or len(value) > 128
                        or value in ('provice', 'province', 'city')
                        or any(ord(c) < 32 for c in value)):
                    raise ValueError('Actual provider geographic codes required')
                result[key] = value
        return result

    def get_shipping_quote(self, product_id, sku_id, quantity=1, ship_to_country='DE',
                           postal_code=None, city=None, province=None):
        """Read-only EUR freight estimate for an explicitly selected current SKU.

        Official schema: https://openservice.aliexpress.com/doc/doc.htm#/?docId=1597
        `code` (not display `company`) is placeorder's logistics_service_name.
        The documented example pairs shipping_fee_cent='172.71' with US $172.71,
        despite the field's misleading name: do NOT divide by 100. City/province
        must be AliExpress address API values, not guessed geographic mappings.
        No postal/street-address request field is documented. This method never
        authorizes a purchase or promotes an estimate to final checkout freight.
        Product details deliberately retain shipping_cost=None. Selects the
        cheapest validated service (then fastest maximum delivery) automatically.
        Conditional platform-free-shipping thresholds are not applied: only an
        explicit free_shipping=true makes the cost zero. Germany/EUR only, as
        current product/stock validation is Germany-specific. Postal-code input
        is rejected rather than silently ignored. Even city/province estimates
        cannot establish street/postal-address applicability or final order tax.
        """
        from datetime import datetime, timezone
        product_id = self._product_id(product_id)
        sku_id = self._product_id(sku_id)
        if type(quantity) is not int or quantity <= 0:
            raise AliExpressCapabilityError('Freight: positive integer quantity required')
        if ship_to_country != 'DE':
            raise AliExpressCapabilityError('Freight: only Germany/EUR is currently supported')
        if postal_code is not None:
            raise AliExpressCapabilityError('Freight: postal-code applicability is not supported by documented API; no address-level quote available')
        if (city is None) != (province is None) or any(
                not isinstance(v, str) or not v.strip() for v in (city, province) if v is not None):
            raise AliExpressCapabilityError('Freight: paired AliExpress city/province values required')
        product = self.get_product_details(product_id)
        matches = [s for s in product['skus'] if s['sku_id'] == sku_id]
        if len(matches) != 1:
            raise AliExpressCapabilityError('Freight: selected SKU does not uniquely match current product')
        stock = self._number(matches[0].get('warehouse_count'), integer=True)
        if stock is None or stock < quantity:
            raise AliExpressCapabilityError('Freight: sufficient known SKU inventory required')
        body = {'quantity':quantity, 'shipToCountry':ship_to_country, 'productId':product_id,
                'selectedSkuId':sku_id, 'currency':'EUR', 'language':'en_US', 'locale':'en_US'}
        if city is not None:
            body.update(cityCode=city, provinceCode=province)
        result = self._request('aliexpress.ds.freight.query', {
            'queryDeliveryReq':json.dumps(body, separators=(',', ':'))}).get('result')
        if not isinstance(result, dict) or result.get('success') is not True or str(result.get('code')) != '200':
            raise AliExpressCapabilityError('Freight: no successful delivery quote returned')
        wrapper = result.get('delivery_options')
        options = wrapper.get('delivery_option_d_t_o') if isinstance(wrapper, dict) else None
        if not isinstance(options, list) or not options:
            raise AliExpressCapabilityError('Freight: no documented delivery options available')
        validated = []
        for option in options:
            if not isinstance(option, dict):
                raise AliExpressAPIError('Freight: malformed delivery option')
            service = option.get('code')
            if (not isinstance(service, str) or not service or len(service) > 128
                    or not service.isascii() or not all(c.isalnum() or c in '_-' for c in service)
                    or option.get('shipping_fee_currency') != 'EUR'
                    or type(option.get('free_shipping')) is not bool):
                raise AliExpressAPIError('Freight: invalid service, currency or free-shipping schema')
            cost = 0.0 if option['free_shipping'] else self._number(option.get('shipping_fee_cent'))
            import math
            if cost is None or not math.isfinite(cost):
                raise AliExpressAPIError('Freight: verified nonnegative freight amount unavailable')
            low = self._number(option.get('min_delivery_days'), integer=True)
            high = self._number(option.get('max_delivery_days'), integer=True)
            if low is None or high is None or high < low:
                raise AliExpressAPIError('Freight: valid delivery estimate unavailable')
            validated.append(dict(option, cost=cost, min_delivery_days=low, max_delivery_days=high))
        selected = min(validated, key=lambda o: (o['cost'], o['max_delivery_days'], o['code']))
        return {'product_id':product_id, 'sku_id':sku_id, 'quantity':quantity,
                'ship_to_country':ship_to_country, 'currency':selected['shipping_fee_currency'],
                'cost':selected['cost'],
                'service_name':selected['code'], 'logistics_service_name':selected['code'],
                'delivery_estimate':{'min_days':selected.get('min_delivery_days'),
                                     'max_days':selected.get('max_delivery_days')},
                'quoted_at':datetime.now(timezone.utc).isoformat(),
                'geographic_scope':'city_province' if city is not None else 'country',
                'city':city, 'province':province, 'is_estimate':True, 'transaction_ready':False}

    def get_product_special_info(self, product_id, country_codes=('DE',)):
        """Supplier-provided qualification claims, NEVER verified compliance.

        Official fields: itemId, countryCodes (String[]), appKey. The official
        SDK example serializes one country as a plain string; only that verified
        single-country form is supported, not an assumed CSV/list wire format.
        Keeps the existing authenticated TOP transport; no anonymous fallback.
        """
        import re
        product_id = self._product_id(product_id)
        if (not isinstance(country_codes, (list, tuple)) or len(country_codes) != 1
                or not isinstance(country_codes[0], str)
                or not re.fullmatch(r'[A-Z]{2}', country_codes[0])):
            raise ValueError('One actual uppercase country code is supported per request')
        self._reload()
        if not self.app_key or self.app_key in ('your app code', 'your appkey'):
            raise AliExpressCapabilityError('Special info requires the configured real application key')
        envelope = self._request('aliexpress.ds.product.specialinfo.get', {
            'itemId':product_id, 'countryCodes':country_codes[0], 'appKey':self.app_key})
        result = envelope.get('result')
        if not isinstance(result, dict) or result.get('ret') not in (True, 'true'):
            raise AliExpressAPIError('Special info: unsuccessful response')
        data = result.get('data')
        if not isinstance(data, dict) or str(data.get('product_id')) != product_id:
            raise AliExpressAPIError('Special info: missing or mismatched product identity')
        rows = data.get('item_qualification_list')
        if not isinstance(rows, list) or any(
                not isinstance(row, dict) or any(not isinstance(row.get(key), str) or not row[key]
                                               for key in ('value_type', 'key', 'value')) for row in rows):
            raise AliExpressAPIError('Special info: unsupported qualification list')
        return dict(data, compliance_verified=False, transaction_ready=False)

    def get_wholesale_product_details(self, product_id, remove_personal_benefit=None):
        """Checked wholesale details, including untouched per-SKU price tiers.

        These are supplier claims, not supplier rights, discounts selected for
        an order, or approval to publish. The regular discovery path is unchanged.
        """
        product_id = self._product_id(product_id)
        params = {'product_id':product_id, 'ship_to_country':'DE',
                  'target_currency':'EUR', 'target_language':'de'}
        if remove_personal_benefit is not None:
            if type(remove_personal_benefit) is not bool:
                raise ValueError('remove_personal_benefit must be a boolean')
            params['remove_personal_benefit'] = str(remove_personal_benefit).lower()
        envelope = self._request('aliexpress.ds.product.wholesale.get', params)
        result = envelope.get('result')
        if envelope.get('rsp_code') not in (200, '200') or not isinstance(result, dict):
            raise AliExpressAPIError('Wholesale: unsuccessful or unsupported product response')
        base = result.get('ae_item_base_info_dto')
        if not isinstance(base, dict) or str(base.get('product_id')) != product_id:
            raise AliExpressAPIError('Wholesale: missing or mismatched product identity')
        skus = result.get('ae_item_sku_info_dtos')
        if isinstance(skus, dict):
            skus = skus.get('ae_item_sku_info_d_t_o')
        if not isinstance(skus, list) or any(not isinstance(sku, dict) for sku in skus):
            raise AliExpressAPIError('Wholesale: unsupported SKU schema')
        return dict(result, ae_item_sku_info_dtos=skus)

    def get_product_details(self, product_id, *, remove_personal_benefit=None,
                            biz_model=None, province_code=None, city_code=None):
        product_id = self._product_id(product_id)
        params = dict(self._geographic_codes(province_code, city_code),
                      product_id=product_id, ship_to_country='DE',
                      target_currency='EUR', target_language='de')
        if remove_personal_benefit is not None:
            if type(remove_personal_benefit) is not bool:
                raise ValueError('remove_personal_benefit must be a boolean')
            params['remove_personal_benefit'] = str(remove_personal_benefit).lower()
        if biz_model is not None:
            if (not isinstance(biz_model, str) or not biz_model.strip() or len(biz_model) > 128
                    or biz_model == 'biz_model' or any(ord(c) < 32 for c in biz_model)):
                raise ValueError('Supply an actual authorized business model or omit it')
            params['biz_model'] = biz_model
        envelope = self._request('aliexpress.ds.product.get', params)
        result = envelope.get('result')
        if not isinstance(result, dict) or not isinstance(result.get('ae_item_base_info_dto'), dict):
            raise AliExpressAPIError('aliexpress.ds.product.get: unsupported product schema')
        base = result['ae_item_base_info_dto']
        returned_id = base.get('product_id')
        if returned_id is not None and str(returned_id) != product_id:
            raise AliExpressAPIError('aliexpress.ds.product.get: mismatched product ID')
        raw = result.get('ae_item_sku_info_dtos', {})
        if isinstance(raw, dict):
            raw = raw.get('ae_item_sku_info_d_t_o', [])
        if not isinstance(raw, list):
            raise AliExpressAPIError('aliexpress.ds.product.get: unsupported SKU schema')
        skus = []
        for sku in raw:
            if not isinstance(sku, dict):
                raise AliExpressAPIError('aliexpress.ds.product.get: malformed SKU record')
            stock_value = sku.get('sku_available_stock', sku.get('ipm_sku_stock'))
            stock = self._number(stock_value, integer=True)
            price = self._number(sku.get('offer_sale_price', sku.get('sku_price'))) if sku.get('currency_code') == 'EUR' else None
            skus.append({'sku_id':str(sku['sku_id']) if sku.get('sku_id') else None,
                         'sku_attr':sku.get('sku_attr') or sku.get('id'), 'warehouse_count':stock,
                         'sale_price':price, 'currency':'EUR' if price is not None else None})
        # Never silently select a variant from a multi-SKU listing.
        selected = skus[0] if len(skus) == 1 else {}
        images = result.get('ae_multimedia_info_dto', {}).get('image_urls')
        image = images.split(';')[0] if isinstance(images, str) and images else None
        # ✅ YASAK KURALI: Her ürün KENDİ görsellerini kullanır - TÜM görselleri döndür
        image_urls = images if isinstance(images, str) and images else None
        return {'product_id':product_id, 'product_title':base.get('subject'),
                'product_main_image_url':image, 'image_urls':image_urls,  # ✅ TÜM görseller
                'sale_price':selected.get('sale_price'),
                'warehouse_count':selected.get('warehouse_count'), 'sku_id':selected.get('sku_id'),
                'shipping_cost':None, 'currency':selected.get('currency'), 'ship_to_country':'DE',
                'skus':skus, 'ae_item_sku_info_dtos':result.get('ae_item_sku_info_dtos'), 'transaction_ready':False}


