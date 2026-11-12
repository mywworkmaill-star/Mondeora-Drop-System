"""Guarded eBay Media API PNG hosting; upload once, verify with GET, never blind retry."""
from contextlib import closing
from datetime import datetime,timezone
import hashlib
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
import requests
from src.listing_assets import validated_asset
from src.runtime import PROJECT_ROOT

MEDIA='https://apim.ebay.com/commerce/media/v1_beta/image'


def _resource(url):
    if not isinstance(url,str):raise ValueError('Missing eBay image resource')
    p=urlsplit(url)
    if (p.scheme!='https' or p.netloc!='apim.ebay.com' or p.query or p.fragment
            or not p.path.startswith('/commerce/media/v1_beta/image/')):
        raise ValueError('Untrusted eBay image resource')
    handle=p.path[len('/commerce/media/v1_beta/image/'):]
    if not handle or len(handle)>512 or '/' in handle or any(ord(c)<33 for c in handle):raise ValueError('Invalid eBay image resource ID')
    return url


def _get(client,resource):
    response=client.session.request('GET',_resource(resource),headers=client._get_headers(),timeout=30,allow_redirects=False)
    if response.status_code!=200:raise ValueError('eBay image readback failed')
    data=response.json()
    if not isinstance(data,dict) or data.get('errors'):raise ValueError('eBay image readback invalid')
    url=data.get('imageUrl');p=urlsplit(url) if isinstance(url,str) else None
    if p is None or p.scheme!='https' or p.username or not (p.hostname or '').endswith('.ebayimg.com'):
        raise ValueError('eBay image readback has no trusted EPS URL')
    expiry=data.get('expirationDate')
    if not isinstance(expiry,str):raise ValueError('Image expiration unverified')
    expires=datetime.fromisoformat(expiry.replace('Z','+00:00'))
    if expires.tzinfo is None or expires<=datetime.now(timezone.utc):raise ValueError('eBay image expired')
    return url,expiry


def host_asset(client,asset,*,root=PROJECT_ROOT):
    client._require_live()
    if str(client._settings().get('ALLOW_EBAY_IMAGE_UPLOADS','')).lower()!='true':
        raise ValueError('Prepared eBay image uploads are not enabled')
    path=validated_asset(asset,root)
    content=path.read_bytes();sha=hashlib.sha256(content).hexdigest()
    if sha!=asset['sha256']:raise ValueError('PNG changed before upload')
    # API does not support animated/multipage PNG. Do not silently strip frames.
    from PIL import Image
    with Image.open(path) as image:
        if getattr(image,'n_frames',1)!=1:raise ValueError('Animated PNG requires separate review')
    database=Path(root)/'data/listing_image_uploads.sqlite3'
    database.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(database,timeout=20)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS uploads (sha TEXT PRIMARY KEY,state TEXT NOT NULL,resource TEXT,url TEXT,expires TEXT)')
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT state,resource FROM uploads WHERE sha=?',(sha,)).fetchone()
        if old is None:db.execute("INSERT INTO uploads(sha,state) VALUES (?, 'pending')",(sha,))
        db.commit()
        if old is not None and not old[1]:raise ValueError('Earlier image upload is pending/uncertain; reconcile before retry')
        resource=old[1] if old else None
        try:
            if resource is None:
                headers=client._get_headers();headers.pop('Content-Type',None)
                # requests supplies multipart/form-data with the required boundary.
                client._require_live()
                response=client.session.request('POST',MEDIA+'/create_image_from_file',headers=headers,
                    files={'image':(path.name,content,'image/png')},timeout=60,allow_redirects=False)
                if response.status_code!=201:raise ValueError('eBay image upload not confirmed')
                resource=_resource(response.headers.get('Location') or response.headers.get('location'))
                db.execute('UPDATE uploads SET resource=? WHERE sha=?',(resource,sha));db.commit()
            url,expiry=_get(client,resource)
            db.execute("UPDATE uploads SET state='verified',url=?,expires=? WHERE sha=?",(url,expiry,sha));db.commit()
            return url
        except Exception:
            db.execute("UPDATE uploads SET state='uncertain' WHERE sha=?",(sha,));db.commit()
            raise ValueError('Prepared image hosting failed or is uncertain; no automatic re-upload') from None
