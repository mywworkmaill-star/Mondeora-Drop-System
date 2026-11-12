"""Production eBay REST client; external writes require explicit opt-in."""
import base64
import hashlib
import json
import os
import re
import stat
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote
from pathlib import Path
import math
import requests
from dotenv import dotenv_values
from src.api.credential_file import credential_lock, merge_credentials_locked

_OAUTH_LOCK = threading.RLock()


class EBayAPIError(RuntimeError):
    """Sanitized failure: deliberately excludes response text and request URLs."""
    status_code = None


class eBayAPIClient:
    production_url = 'https://api.ebay.com'
    current_url = production_url
    inventory_path = '/sell/inventory/v1'
    max_pages = 1000

    def __init__(self, session=None, env_path=None, config=None):
        self.env_path = Path(env_path or Path(__file__).resolve().parents[2] / '.env').resolve()
        self.session = session if session is not None else requests.Session()
        self.config = dict(config or {})
        self.last_error = None

    def _settings(self):
        settings = {**os.environ, **dotenv_values(self.env_path), **self.config}
        # Resolve token aliases by source, not by their spelling. Explicit
        # injection wins; otherwise the latest file wins over loaded env values.
        for generic, specific in (('ACCESS_TOKEN', 'EBAY_ACCESS_TOKEN'), ('REFRESH_TOKEN', 'EBAY_REFRESH_TOKEN')):
            for source in (self.config, dotenv_values(self.env_path), os.environ):
                if generic in source or specific in source:
                    value = source.get(specific) if specific in source else source.get(generic)
                    settings[generic] = settings[specific] = value
                    break
        return settings

    @property
    def metadata_path(self):
        return self.env_path.parent / 'data' / 'ebay_oauth_metadata.json'

    @property
    def access_token(self):
        return self._settings().get('EBAY_ACCESS_TOKEN')

    def _get_headers(self):
        token = self.access_token
        if not token:
            self._fail('eBay access token missing')
        settings = self._settings()
        return {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
                'Content-Language': settings.get('EBAY_CONTENT_LANGUAGE', 'de-DE'),
                'Accept-Language': 'de-DE', 'X-EBAY-C-MARKETPLACE-ID': 'EBAY_DE'}

    def _fail(self, message, status_code=None):
        self.last_error = message
        error = EBayAPIError(message)
        error.status_code = status_code
        raise error from None

    def _request(self, method, path, **kwargs):
        if not path.startswith('/') or '?' in path or '#' in path or '://' in path:
            self._fail('Invalid eBay API path')
        if method != 'GET':
            self._require_live()
        refreshed = False
        retries = 0
        MAX_RETRIES = 3
        # Idempotent methods (GET/PUT: same payload = same end state) retry on network errors + 429/5xx.
        # POST/DELETE can have side effects, so a 5xx (ambiguous: may already have executed) is never retried
        # — only 429 (rate-limited BEFORE the server did anything) is safe to retry for them.
        idempotent = method in ('GET', 'PUT')
        while True:
            try:
                response = self.session.request(method, self.production_url + path,
                    headers=self._get_headers(), timeout=30, allow_redirects=False, **kwargs)
            except requests.RequestException:
                if idempotent and retries < MAX_RETRIES:
                    retries += 1
                    time.sleep(min(0.5 * 2 ** retries, 8.0))
                    continue
                self._fail('eBay network request failed')
            if response.status_code == 401 and not refreshed:
                refreshed = True
                result = self.refresh_access_token(force=True)
                if not result['success']:
                    self._fail('eBay authentication failed; OAuth renewal unsuccessful')
                continue
            retryable = response.status_code == 429 or (idempotent and response.status_code in (500, 502, 503, 504))
            if retryable and retries < MAX_RETRIES:
                retries += 1
                time.sleep(min(0.5 * 2 ** retries, 8.0))
                continue
            if not 200 <= response.status_code < 300:
                self._fail('eBay API request failed (HTTP %d)' % response.status_code, response.status_code)
            if (method == 'POST' and response.status_code == 201
                    and re.fullmatch(r'/sell/fulfillment/v1/order/[^/]+/shipping_fulfillment', path)
                    and getattr(response, 'content', None) == b''):
                # This endpoint documents 201 with no body. Return only a tightly
                # scoped resource ID, never response/request headers or arbitrary URLs.
                location = getattr(response, 'headers', {}).get('Location', '')
                prefix = self.production_url + path + '/'
                handle = location[len(prefix):] if isinstance(location, str) and location.startswith(prefix) else ''
                self.last_error = None
                return {'fulfillmentId': handle} if re.fullmatch(r'[A-Za-z0-9_-]{1,128}', handle) else {}
            if response.status_code == 204:
                if method == 'GET':
                    self._fail('eBay returned an empty read response')
                self.last_error = None
                return {}
            try:
                data = response.json()
            except (ValueError, TypeError):
                self._fail('eBay returned invalid JSON')
            if not isinstance(data, dict) or (method == 'GET' and not data):
                self._fail('eBay returned invalid response structure')
            if data.get('errors'):
                self._fail('eBay returned business errors')
            self.last_error = None
            return data

    @staticmethod
    def _atomic_write(path, text):
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

    def refresh_access_token(self, force=False):
        """Renew user OAuth token. Returns metadata only; never credentials."""
        try:
            return self._refresh_access_token_locked(force)
        except OSError:
            self.last_error = 'eBay OAuth configuration locked or unavailable'
            return {'success': False, 'expires_at': None, 'error': self.last_error}

    def _refresh_access_token_locked(self, force):
        with _OAUTH_LOCK, credential_lock(self.env_path):
            try:
                metadata = json.loads(self.metadata_path.read_text(encoding='utf-8'))
                token_hash = hashlib.sha256((self.access_token or '').encode()).hexdigest()
                if (not force and self.access_token and metadata.get('token_sha256') == token_hash
                        and math.isfinite(float(metadata.get('expires_at', 0)))
                        and float(metadata.get('expires_at', 0)) > time.time() + 120):
                    return {'success': True, 'expires_at': metadata['expires_at'], 'cached': True}
            except (OSError, ValueError, TypeError, OverflowError, AttributeError):
                pass
            settings = self._settings()
            refresh = settings.get('REFRESH_TOKEN') or settings.get('EBAY_REFRESH_TOKEN')
            app, secret = settings.get('EBAY_APP_ID'), settings.get('EBAY_CERT_ID')
            if not isinstance(app, str) or not app or not isinstance(secret, str) or not secret or not isinstance(refresh, str) or not refresh:
                self.last_error = 'OAuth configuration missing'
                return {'success': False, 'expires_at': None, 'error': self.last_error}
            basic = base64.b64encode((app + ':' + secret).encode()).decode('ascii')
            try:
                response = self.session.request('POST', self.production_url + '/identity/v1/oauth2/token',
                    headers={'Authorization': 'Basic ' + basic, 'Content-Type': 'application/x-www-form-urlencoded'},
                    data={'grant_type': 'refresh_token', 'refresh_token': refresh}, timeout=30, allow_redirects=False)
                if response.status_code != 200:
                    self._fail('eBay OAuth request failed (HTTP %d)' % response.status_code)
                body = response.json()
                token, raw_expiry = body.get('access_token'), body.get('expires_in', 0)
                expires = float(raw_expiry)
                if isinstance(raw_expiry, bool) or not math.isfinite(expires) or not expires.is_integer():
                    self._fail('eBay OAuth response invalid')
                if not isinstance(token, str) or not token or any(c in token for c in '\r\n') or expires <= 0:
                    self._fail('eBay OAuth response invalid')
                updates = {'ACCESS_TOKEN': token, 'EBAY_ACCESS_TOKEN': token}
                rotated = body.get('refresh_token')
                if rotated is not None:
                    updates.update(REFRESH_TOKEN=rotated, EBAY_REFRESH_TOKEN=rotated)
                merge_credentials_locked(self.env_path, updates)
                # Existing process/injected tokens must not shadow the renewed token.
                for source in (self.config, os.environ):
                    for key, value in updates.items():
                        if key in source:
                            source[key] = value
                expires_at = time.time() + expires
                metadata = {'expires_at': expires_at, 'issued_at': time.time(),
                            'token_sha256': hashlib.sha256(token.encode()).hexdigest()}
                self._atomic_write(self.metadata_path, json.dumps(metadata, indent=2) + '\n')
                self.last_error = None
                return {'success': True, 'expires_at': expires_at, 'cached': False}
            except (requests.RequestException, OSError, ValueError, TypeError, OverflowError, AttributeError, EBayAPIError):
                # Exceptions and response bodies can contain credentials. Never propagate.
                self.last_error = 'eBay OAuth renewal or token persistence failed'
                return {'success': False, 'expires_at': None, 'error': self.last_error}

    def check_token_validity(self):
        try:
            self._request('GET', self.inventory_path + '/inventory_item', params={'limit': 1})
            return True
        except EBayAPIError:
            return False

    def _require_live(self):
        from src.runtime import writes_allowed
        if not writes_allowed(self._settings()):
            raise PermissionError('Canli eBay yazma islemleri kapali: yazma izni ve tedarikci anlasmasi gerekli.')

    def _pages(self, path, key, params=None, limit=200):
        """Use local offsets, never follow server-supplied URLs with credentials."""
        offset = 0
        seen = set()
        for _ in range(self.max_pages):
            page = self._request('GET', path, params={**(params or {}), 'limit': limit, 'offset': offset})
            values = page.get(key, [] if page.get('total') == 0 else None)
            total = page.get('total')
            if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
                self._fail('eBay pagination response invalid')
            if total is not None and (not isinstance(total, int) or total < 0):
                self._fail('eBay pagination total invalid')
            fingerprint = json.dumps(values, sort_keys=True)
            if values and fingerprint in seen:
                self._fail('eBay pagination repeated a page')
            seen.add(fingerprint)
            if not values:
                if page.get('next') or (total is not None and offset < total):
                    self._fail('eBay pagination ended before advertised total')
                return
            yield from values
            offset += len(values)
            if total is not None:
                if offset >= total:
                    return
            elif not page.get('next') and len(values) < limit:
                return
        self._fail('eBay pagination safety limit reached')

    def get_orders(self, status='NOT_STARTED', days_back=30):
        """Return paid, uncancelled, unfulfilled orders; API failure always raises."""
        if isinstance(days_back, bool) or not isinstance(days_back, int) or not 1 <= days_back <= 90:
            raise ValueError('days_back must be an integer from 1 to 90')
        # Compatibility with the former engine, without sending invalid enum values.
        if status in ('All', 'ALL', 'RequiresShippingAddress'):
            statuses = ('NOT_STARTED', 'IN_PROGRESS')
        elif status in ('NOT_STARTED', 'IN_PROGRESS'):
            statuses = (status,)
        else:
            raise ValueError('Only unfulfilled order statuses are supported')
        now = datetime.now(timezone.utc)
        stamp = lambda value: value.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        # eBay supports the combined pair, not a singleton status filter.
        # Narrow to the requested status locally after fetching all pages.
        filters = 'creationdate:[%s..%s],orderfulfillmentstatus:{NOT_STARTED|IN_PROGRESS}' % (
            stamp(now - timedelta(days=days_back)), stamp(now))
        result, ids = [], set()
        for order in self._pages('/sell/fulfillment/v1/order', 'orders', {'filter': filters}):
            order_id = order.get('orderId')
            if not order_id or order_id in ids:
                self._fail('eBay order pagination missing or duplicated order ID')
            ids.add(order_id)
            if (order.get('orderPaymentStatus') == 'PAID'
                    and order.get('orderFulfillmentStatus') in statuses
                    and order.get('cancelStatus', {}).get('cancelState', 'NONE_REQUESTED') == 'NONE_REQUESTED'):
                result.append(order)
        return result

    @staticmethod
    def _identifier(value, name):
        if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
            raise ValueError(name + ' must be a nonempty identifier')
        return value

    @staticmethod
    def _quantity(value):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError('quantity must be a nonnegative integer')
        return value

    @staticmethod
    def _price(value):
        try:
            number = Decimal(str(value))
            if not number.is_finite() or number <= 0:
                raise ValueError('price must be positive and finite')
            return format(number, 'f')
        except (InvalidOperation, TypeError):
            raise ValueError('price must be positive and finite') from None

    def list_product_fixed_price(self, data):
        """Stage inventory and offer, then publish. Partial failures retain offer ID.

        No rollback/retry: a timeout may mean a write succeeded remotely. Inspect
        returned identifiers and seller inventory before manually trying again.
        """
        self._require_live()
        settings = self._settings()
        category = data.get('category_id') or settings.get('CATEGORY_DE') or settings.get('EBAY_CATEGORY_DE')
        policies = {
            'paymentPolicyId': settings.get('PAYMENT_POLICY_ID') or settings.get('EBAY_PAYMENT_POLICY_ID'),
            'fulfillmentPolicyId': settings.get('FULFILLMENT_POLICY_ID') or settings.get('EBAY_FULFILLMENT_POLICY_ID'),
            'returnPolicyId': settings.get('RETURN_POLICY_ID') or settings.get('EBAY_RETURN_POLICY_ID')}
        for name, value in {'categoryId': category, **policies}.items():
            if not isinstance(value, str) or not re.fullmatch(r'[0-9]+', value) or int(value) <= 0:
                raise ValueError(name + ' requires a configured non-placeholder numeric ID')
        location = settings.get('EBAY_MERCHANT_LOCATION_KEY')
        if not isinstance(location, str) or not location or location.lower() in ('default', 'placeholder', 'changeme', 'your_location_key'):
            raise ValueError('EBAY_MERCHANT_LOCATION_KEY must reference an existing enabled inventory location')
        sku = self._identifier(data.get('sku'), 'sku')
        if len(sku) > 50:
            raise ValueError('sku exceeds 50 characters')
        quantity, price = self._quantity(data.get('quantity')), self._price(data.get('price'))
        for key in ('title', 'description'):
            if not isinstance(data.get(key), str) or not data[key].strip():
                raise ValueError(key + ' required')
        from src.listing_assets import listing_images
        from src.ebay_image_hosting import host_asset
        images = listing_images(data, root=self.env_path.parent,
            publisher=lambda asset: host_asset(self, asset, root=self.env_path.parent))
        if images is None:
            images = data.get('image_urls') or [data.get('image_url')]
        if not isinstance(images, list) or not images or any(not isinstance(u, str) or not u.startswith('https://') for u in images):
            raise ValueError('HTTPS image URLs required')
        product = {'title': data['title'], 'description': data['description'], 'imageUrls': images}
        for key in ('aspects', 'brand', 'mpn', 'ean', 'upc'):
            if key in data:
                product[key] = data[key]
        inventory = {'availability': {'shipToLocationAvailability': {'quantity': quantity}},
                     'condition': data.get('condition', 'NEW'), 'product': product}
        if data.get('condition_description'):
            inventory['conditionDescription'] = data['condition_description']
        if data.get('package_weight_and_size'):
            inventory['packageWeightAndSize'] = data['package_weight_and_size']
        offer = {'sku': sku, 'marketplaceId': 'EBAY_DE', 'format': 'FIXED_PRICE',
                 'availableQuantity': quantity, 'categoryId': category, 'merchantLocationKey': location,
                 'listingPolicies': policies, 'listingDescription': data['description'],
                 'listingDuration': 'GTC', 'includeCatalogProductDetails': False,
                 'pricingSummary': {'price': {'currency': 'EUR', 'value': price}}}
        result = {'success': False, 'ebay_item_id': None, 'offer_id': None, 'sku': sku}
        try:
            self._request('PUT', self.inventory_path + '/inventory_item/' + quote(sku, safe=''), json=inventory)
            created = self._request('POST', self.inventory_path + '/offer', json=offer)
            offer_id = created.get('offerId')
            if not isinstance(offer_id, str) or not offer_id:
                self._fail('eBay createOffer returned no offer ID')
            result['offer_id'] = offer_id
            published = self._request('POST', self.inventory_path + '/offer/' + quote(offer_id, safe='') + '/publish')
            listing_id = published.get('listingId')
            if not isinstance(listing_id, str) or not listing_id:
                self._fail('eBay publishOffer returned no listing ID')
            result.update(success=True, ebay_item_id=listing_id)
        except EBayAPIError:
            result['error'] = self.last_error
        return result

    def _offers(self, sku):
        try:
            return list(self._pages(self.inventory_path + '/offer', 'offers', {'sku': sku}, limit=100))
        except EBayAPIError as error:
            # A valid inventory SKU can have no offer yet (documented HTTP 404).
            if error.status_code == 404:
                self.last_error = None
                return []
            raise

    def _bulk(self, request):
        result = self._request('POST', self.inventory_path + '/bulk_update_price_quantity', json={'requests': [request]})
        responses = result.get('responses')
        if (result.get('errors') or not isinstance(responses, list) or not responses
                or any(not isinstance(r, dict) or r.get('statusCode') != 200 or r.get('errors') for r in responses)):
            self._fail('eBay bulk update failed or returned incomplete results')
        expected = {o['offerId'] for o in request.get('offers', [])}
        returned = {r.get('offerId') for r in responses if r.get('offerId')}
        if expected != returned:
            self._fail('eBay bulk update did not confirm every requested offer')
        if not expected and not any(r.get('sku') == request['sku'] for r in responses):
            self._fail('eBay bulk update did not confirm the inventory SKU')
        return True

    def update_inventory(self, sku, quantity):
        self._require_live()
        sku, quantity = self._identifier(sku, 'sku'), self._quantity(quantity)
        try:
            offers = self._offers(sku)
            # Never silently change auction allocations or other marketplaces.
            if any(o.get('format') != 'FIXED_PRICE' or o.get('marketplaceId') != 'EBAY_DE' or not o.get('offerId') for o in offers):
                self._fail('Unsupported offer format or marketplace for quantity update')
            payload = {'sku': sku, 'shipToLocationAvailability': {'quantity': quantity}}
            if offers:
                payload['offers'] = [{'offerId': o['offerId'], 'availableQuantity': quantity} for o in offers]
            return self._bulk(payload)
        except EBayAPIError:
            return False

    def update_price(self, sku, price, offer_id=None):
        self._require_live()
        sku, price = self._identifier(sku, 'sku'), self._price(price)
        if offer_id is not None:
            self._identifier(offer_id, 'offer_id')
        try:
            if offer_id is not None:
                offer = self._request('GET', self.inventory_path + '/offer/' + quote(offer_id, safe=''))
                if offer.get('sku') != sku:
                    self._fail('Offer does not belong to supplied SKU')
                offers = [offer]
            else:
                offers = self._offers(sku)
            if not offers:
                self._fail('No offers found for price update')
            updates = []
            for offer in offers:
                if offer.get('marketplaceId') != 'EBAY_DE' or offer.get('format') != 'FIXED_PRICE' or not offer.get('offerId'):
                    self._fail('Unsupported offer format or marketplace for price update')
                currency = offer.get('pricingSummary', {}).get('price', {}).get('currency')
                if currency != 'EUR':
                    self._fail('Offer currency must be EUR for Germany')
                updates.append({'offerId': offer['offerId'], 'price': {'currency': currency, 'value': price}})
            return self._bulk({'sku': sku, 'offers': updates})
        except EBayAPIError:
            return False

    def _listing_offer(self, item_id):
        """Inventory has no listing/{id} lookup: resolve listing through SKU offers.

        Only Inventory-managed single-variation offers are supported. No Trading
        XML migration/fallback and no silent modifications to unrelated listings.
        """
        self._identifier(item_id, 'ebay_item_id')
        for inventory in self._pages(self.inventory_path + '/inventory_item', 'inventoryItems'):
            sku = inventory.get('sku')
            if not isinstance(sku, str) or not sku:
                self._fail('Inventory response missing SKU')
            for offer in self._offers(sku):
                if offer.get('listing', {}).get('listingId') == item_id:
                    if not offer.get('offerId'):
                        self._fail('Inventory offer missing offer ID')
                    return sku, offer
        self._fail('Listing not found among Inventory-managed offers; legacy listings require explicit migration')

    def end_listing(self, ebay_item_id, reason='OutOfStock'):
        """Withdraw the matched offer. Inventory withdraw has no reason parameter."""
        self._require_live()
        self._identifier(ebay_item_id, 'ebay_item_id')
        try:
            sku, offer = self._listing_offer(ebay_item_id)
            if offer.get('inventoryItemGroupKey'):
                self._fail('Grouped listings require explicit withdrawOfferByInventoryItemGroup')
            result = self._request('POST', self.inventory_path + '/offer/' + quote(offer['offerId'], safe='') + '/withdraw')
            if result.get('listingId') != ebay_item_id:
                self._fail('eBay withdraw response did not confirm the requested listing')
            return True
        except EBayAPIError:
            return False

    def get_product_details(self, ebay_item_id):
        sku, offer = self._listing_offer(ebay_item_id)
        inventory = self._request('GET', self.inventory_path + '/inventory_item/' + quote(sku, safe=''))
        return {'ebay_item_id': ebay_item_id, 'sku': sku, 'offer_id': offer['offerId'],
                'offer': offer, 'inventory_item': inventory}


class eBayRESTClient(eBayAPIClient):
    """Browse search sharing the same OAuth and sanitized request handling."""
    base_url = 'https://api.ebay.com/buy/browse/v1'

    def search_products(self, keyword, category=None, limit=50):
        if not isinstance(keyword, str) or not keyword.strip():
            raise ValueError('keyword required')
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError('limit must be from 1 to 200')
        params = {'q': keyword, 'limit': limit, 'sort': 'price'}
        if category is not None:
            params['category_ids'] = category
        data = self._request('GET', '/buy/browse/v1/item_summary/search', params=params)
        items = data.get('itemSummaries', [] if data.get('total', 0) == 0 else None)
        if not isinstance(items, list):
            self._fail('eBay Browse response invalid')
        return items
