"""Read-only live completion monitor. Percent is passed / 25 fixed acceptance checks."""
import ast
from datetime import datetime,timezone
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit
import urllib.request

HERE=Path(__file__).resolve().parent
PROJECT=Path('C:/Users/Administrator/Desktop/Mondeora-Drop-System')
LOCK=threading.RLock()
EVENTS=[]
SEEN={}


def progress_summary(rows):
    ids=[r['id'] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate acceptance criterion')
    n=sum(r.get('verified') is True for r in rows)
    return {'verified':n,'total':len(rows),'percent':round(100*n/len(rows),1) if rows else 0}


def read_json(path):
    try:
        if path.stat().st_size>4000000:return {}
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


def fingerprint(project):
    digest=hashlib.sha256()
    try:
        paths=[project/'main.py',project/'requirements.txt',*sorted((project/'src').rglob('*.py'))]
        for p in paths:digest.update(p.relative_to(project).as_posix().encode());digest.update(p.read_bytes())
        return digest.hexdigest()
    except OSError:return None


JOB_NAMES={'operations','orders','fulfillment','inventory','products','research','prices','ebay_token','aliexpress_token'}
JOB_STATUSES={'success','failed','partial_success','error','ok','skipped','blocked','read_only','not_configured'}
EVENT_OPERATIONS={'access_diagnosis','access_probe','access_verification','capability_probe','checkout_probe','mailbox_probe','payment_probe','product_research','product_verification','candidate_validation','source_refresh','market_comparison','evidence_review','monitor_implementation','monitor_verification','monitor_ui_verification'}
EVENT_OPERATIONS.update({'country_freight_quote','evidence_aggregation','market_item_detail','provider_document_review','source_sku_verification','supplier_discovery','checkout_preview_access','configured_mailbox_access','gmail_connector_status','mailbox_fixture_verification','mailbox_status_patch_fixture'})
EVENT_OPERATIONS.update({'research_rotation_fix','gmail_ingestion_fix','regression_verification'})
EVENT_STATUSES={'started','completed','blocked','error','failed'}


def timestamp(value):
    try:
        dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return dt.astimezone(timezone.utc).isoformat() if dt.tzinfo else None
    except (ValueError,TypeError):return None


def runtime_status():
    observed=datetime.now(timezone.utc).isoformat()
    try:
        with urllib.request.urlopen('http://127.0.0.1:5000/api/health',timeout=1) as response:
            body=json.loads(response.read(65537))
        jobs=sorted({name for name in body.get('jobs',[]) if name in JOB_NAMES})
        last={name:(value.get('status') if value.get('status') in JOB_STATUSES else 'reported')
              for name,value in body.get('last_results',{}).items() if name in JOB_NAMES and isinstance(value,dict)}
        # Health currently has no execution timestamps. Observation time is NOT execution time.
        return {'reachable':True,'running':body.get('running') is True,'live_writes':body.get('live_writes') is True,
                'purchases_enabled':body.get('purchases_enabled') is True,'jobs':jobs,'last_jobs':last,
                'observed_at':observed,'job_details':[{'name':name,'registered':name in jobs,
                'execution_observed':name in last,'status':last.get(name,'unknown'),
                'executed_at':None,'observed_at':observed} for name in sorted(set(jobs)|set(last))]}
    except (OSError,ValueError,TypeError,AttributeError):
        return {'reachable':False,'running':False,'jobs':[],'last_jobs':{},'job_details':[],'observed_at':observed}


def workstream_events(project,now):
    events=[];streams=[]
    for stream in ('product','access','monitor','loop_fix','gmail_fix'):
        path=project/'data/parallel_work'/stream/'events.jsonl';collected=[]
        try:
            # Bounded tail, never read delegation logs, raw outputs or arbitrary paths.
            with path.open('rb') as handle:
                handle.seek(max(0,path.stat().st_size-131072));raw=handle.read(131072)
            for line in raw.decode('utf-8',errors='replace').splitlines():
                try:item=json.loads(line)
                except ValueError:continue
                if not isinstance(item,dict):continue
                at=timestamp(item.get('timestamp',item.get('timestamp_utc',item.get('at'))))
                operation=item.get('operation');status=item.get('status')
                if not at or not isinstance(operation,str) or not isinstance(status,str) or operation not in EVENT_OPERATIONS or status not in EVENT_STATUSES:continue
                counts={k:v for k,v in item.get('counts',{}).items() if k in {'tests','failures','errors','candidates','drafts','ready','checks','passed','blocked'} and type(v) is int and 0<=v<=1000000} if isinstance(item.get('counts'),dict) else {}
                collected.append({'at':at,'stream':stream,'operation':operation,'status':status,'counts':counts})
        except OSError:pass
        collected.sort(key=lambda e:e['at']);events.extend(collected[-30:])
        latest=collected[-1] if collected else None
        age=(now-datetime.fromisoformat(latest['at'])).total_seconds() if latest else None
        state='unknown' if latest is None else ('stale' if age<0 or age>300 else latest['status'])
        streams.append({'id':stream,'state':state,'last_observed_at':latest['at'] if latest else None,
                        'last_operation':latest['operation'] if latest else None,'source':f'data/parallel_work/{stream}/events.jsonl',
                        'note':'Başladı kaydı sürekli çalışıyor demek değildir; 5 dakika sonra eski gözlem.'})
    return sorted(events,key=lambda e:e['at'],reverse=True)[:60],streams


def stage_tree(rows,values,project,runtime,tests_current,deploy_current,now):
    lookup={r['id']:r for r in rows}; stages=[]
    paths={'tests':'data/software_verification.json','deploy':'data/deployment_verification.json',
           'research':'data/production_sourcing_v2_verification.json','prepared':'data/production_sourcing_v2_prepared.json',
           'readiness':'data/completion_readiness_offline.json','observations':'data/completion_monitor_observations.json',
           'selection':'data/listing_asset_selection_v2.json','location':'data/ebay_location_review.json'}
    def step(key,title,status,owner,evidence,detail='',observed_at=None):
        return dict(id=key,title=title,status=status,owner=owner,evidence=evidence,detail=detail,observed_at=timestamp(observed_at))
    def criterion(key):
        r=lookup[key]
        return step(key,r['title'],'verified' if r['verified'] else 'blocked',r['owner'],[],r['detail'])
    def report(key,field,title,owner='Ben'):
        value=values[key].get(field)
        return step(key+'_'+field,title,'observed' if value is not None else 'unknown',owner,[paths[key]],
                    str(value) if type(value) in (int,float,bool) else 'Rapor alanı mevcut.' if value is not None else 'Kanıt alanı yok.',
                    values[key].get('observed_at',values[key].get('generated_at')))
    def source(name,title):
        exists=(project/name).is_file()
        return step(name,title,'observed' if exists else 'unknown','Ben',[name],
                    'Kaynak dosyası mevcut; canlı çalıştırma veya yetki kanıtı değildir.' if exists else 'Kaynak dosyası bulunamadı.')
    def add(letter,title,layer,checks,evidence,extra=()):
        children=[criterion(key) for key in checks]+list(extra)
        for child in children:
            if not child['evidence']:child['evidence']=evidence
        counts={status:sum(c['status']==status for c in children) for status in ('verified','observed','blocked','unknown')}
        stages.append(dict(id=letter,title=title,layer=layer,substeps=children,counts=counts))
    add('A','Çalışma ortamı ve kaynak','software',['runtime'],['main.py','src/'])
    add('B','Testler ve sürüm geçerliliği','software',['suite'],[paths['tests']],
        [report('tests','tests_run','Tam koşuda çalıştırılan test'),report('tests','skips','Atlanan test; canlı kanıt sayılmaz'),
         step('test_binding','Kaynak parmak izi eşleşmesi','verified' if tests_current else 'blocked','Ben',[paths['tests']],'Güncel kaynakla eşleşen sıfır hata/başarısızlık koşusu gerekir.')])
    add('C','Salt-okunur güvenlik','software',['readonly'],[paths['deploy']])
    jobs=[step('job_'+j['name'],j['name'],'observed' if j['execution_observed'] else 'unknown','Zamanlayıcı',['http://127.0.0.1:5000/api/health'],
        ('Sonuç gözlendi: '+j['status']+'. Çalışma zamanı raporlanmıyor.' if j['execution_observed'] else 'Yalnız kayıtlı; çalıştırıldığı kanıtlanmadı.'),j['observed_at']) for j in runtime['job_details']]
    add('D','Zamanlayıcı: kayıt ≠ çalıştırma','operational',['heartbeat'],[paths['deploy']],jobs)
    add('E','OAuth yenileme gözlemi','operational',[],['http://127.0.0.1:5000/api/health'],
        [step('token_'+name,name,'observed' if name in runtime['last_jobs'] else 'unknown','Zamanlayıcı',['http://127.0.0.1:5000/api/health'],runtime['last_jobs'].get(name,'Henüz sonuç yok.')) for name in ('ebay_token','aliexpress_token')])
    add('F','eBay canlı okuma','evidence',['ebay_read'],[paths['observations']])
    add('G','Tedarikçi SKU fiyat ve stok','evidence',['supplier_read'],[paths['observations']])
    add('H','Niş araştırması ve taslak','operational',['sourcing'],[paths['research'],paths['prepared']],
        [report('research',field,title) for field,title in [('candidate_count','Gerçek aday sayısı'),('draft_ready_count','Taslak sayısı'),('source_refresh_success_count','Başarılı kaynak yenileme')]])
    add('I','Ürün ilişkisi ve SKU seçimi','evidence',[],[paths['prepared']],
        [report('research','source_refresh_success_count','Yenilenmiş ürün kanıtı'),report('research','exact_sku_png_count','Tam SKU görsel eşleştirme sayısı')])
    add('J','Talep, karşılaştırma ve ticari eleme','evidence',['product_profit'],[paths['prepared'],paths['research']],
        [report('research','commercial_rejection_count','Ticari eleme sayısı'),report('research','publish_ready_count','Yayıma hazır ürün sayısı')])
    add('K','Ücret ve sipariş finansı','software',['fees','order_finance'],[paths['readiness'],paths['tests']])
    add('L','Checkout maliyet kanıtı','evidence',['checkout'],[paths['readiness']])
    add('M','SKU görsel dosyaları','evidence',['images'],[paths['selection']])
    add('N','Taslak ve görsel bağlama','operational',[],[paths['research']],
        [report('research','image_attached_draft_count','Görsel bağlı taslak'),report('research','draft_ready_count','Olgusal taslak; yayın izni değildir')])
    add('O','Gerçek görsel barındırma','evidence',['hosting'],[paths['observations']])
    add('P','Üretici ve ürün güvenliği','evidence',['safety'],[paths['prepared']],
        [report('research','manufacturer_identity_complete_count','Tam üretici kimliği kanıtı','Tedarikçi')])
    add('Q','Ticari görsel hakları','evidence',['rights'],[paths['prepared']])
    add('R','Tedarikçi koşulları','evidence',['supplier_terms'],[paths['readiness'],paths['prepared']])
    add('S','Gerçek depo ve konum','evidence',['warehouse'],[paths['location'],paths['readiness']])
    add('T','Sipariş yürütme ve limitler','software',[],['src/automation/engine.py'],
        [source('src/automation/engine.py','Sipariş orkestratörü'),source('src/automation/spending.py','Harcama koruma kaynağı'),
         step('order_execution','Gerçek sipariş tamamlanması','unknown','Canlı kabul',[paths['readiness']],'Kayıtlı orders işi, satın alma veya teslimat kanıtı değildir.')])
    add('U','Ödeme ve uzlaştırma','evidence',['payment'],[paths['readiness']],
        [source('src/payment_executor.py','Ödeme yürütme kaynağı')])
    add('V','Takip ve uçtan uca kabul','evidence',['tracking'],[paths['readiness']])
    add('W','Posta erişimi ve takip ipuçları','evidence',['email'],[paths['observations']],
        [source('src/email_tracking.py','Posta ayrıştırma kaynağı; canlı erişim değildir')])
    add('X','Süreç kurtarma ve yedek','operational',['restart','backup'],[paths['deploy']])
    add('Y','Kalıcı başlangıç ve reboot','operational',['startup'],[paths['deploy']])
    add('Z','Ticari hesap ve vergi','evidence',['commercial','tax'],[paths['readiness']])
    return stages


def snapshot(project=PROJECT):
    data=project/'data';now=datetime.now(timezone.utc)
    files={
      'tests':data/'software_verification.json','deployment':data/'deployment_verification.json',
      'research':data/'production_sourcing_v2_verification.json','prepared':data/'production_sourcing_v2_prepared.json',
      'readiness':data/'completion_readiness_offline.json','observations':data/'completion_monitor_observations.json',
      'location':data/'ebay_location_review.json','selection':data/'listing_asset_selection_v2.json'}
    values={k:read_json(p) for k,p in files.items()}
    tests=values['tests'];deploy=values['deployment'];research=values['research'];prepared=values['prepared']
    current=fingerprint(project)
    tests_current=bool(current and tests.get('passed') is True and tests.get('failures')==0 and tests.get('errors')==0 and tests.get('source_fingerprint')==current)
    deploy_current=bool(current and deploy.get('passed') is True and deploy.get('source_stable') is True and deploy.get('source_fingerprint')==current)
    readiness={c.get('name'):c for c in values['readiness'].get('checks',[])}
    def passed(name):return readiness.get(name,{}).get('passed') is True
    obs=values['observations'];api=obs.get('api_reads',{})
    try:fresh=0<=(now-datetime.fromisoformat(obs['observed_at'])).total_seconds()<86400
    except (KeyError,ValueError,TypeError):fresh=False
    rows=[]
    def add(key,title,ok,owner,detail,group='technical'):
        rows.append({'id':key,'title':title,'verified':bool(ok),'owner':owner,'detail':detail,'group':group})
    syntax=False
    try:
        paths=[project/'main.py',*list((project/'src').rglob('*.py'))]
        for p in paths:ast.parse(p.read_text(encoding='utf-8-sig'))
        syntax=bool((project/'main.py').exists() and len(paths)>1)
    except (OSError,SyntaxError,UnicodeError):pass
    add('runtime','Python 3.11 ve kaynak sözdizimi',sys.version_info[:2]==(3,11) and syntax,'Ben','Gerçek yorumlayıcı ve tüm runtime kaynakları kontrol edilir.')
    add('suite','Güncel sürümün tam regresyonu',tests_current,'Ben',f"Son koşu: {tests.get('tests_run','—')} test, {tests.get('failures','—')} başarısızlık, {tests.get('errors','—')} hata; sürüm eşleşmesi: {'evet' if tests.get('source_fingerprint')==current else 'hayır'}.")
    add('ebay_read','eBay envanter ve sipariş okuması',fresh and api.get('ebay_inventory') is True and api.get('ebay_orders') is True,'Erişim','Son gerçek API okuması: '+str(obs.get('observed_at','yok')),'access')
    add('supplier_read','AliExpress seçili SKU fiyat/stok okuması',fresh and api.get('aliexpress_selected_sku') is True,'Erişim','Son gerçek API okuması; nihai checkout maliyeti anlamına gelmez.','access')
    checks=deploy.get('runs',[{}])[0].get('http',{}) if deploy.get('runs') else {}
    add('readonly','Yetkisiz komut ve canlı yazma korumaları',deploy_current and checks.get('POST /api/sync/orders unauthorized')==403,'Ben','Gerçek HTTP kontrolü; yayın/satın alma/ödeme açılmaz.')
    add('restart','Tek süreç, kapanış ve çökme sonrası yeniden açılış',deploy_current and deploy.get('all_children_exited') is True and len(deploy.get('runs',[]))>=3,'Ben','Gerçek süreçler ve eski kilit dosyasıyla yeniden başlatma.')
    backup=deploy.get('backup_restore',{})
    add('backup','Gerçek veritabanı yedeği ve izole geri yükleme',deploy_current and backup.get('manifest_hash_verified') is True and backup.get('isolated_restore_integrity')=='ok' and backup.get('table_counts_match') is True,'Ben','SHA-256, SQLite integrity_check ve kayıt sayımları.')
    add('heartbeat','Zamanlayıcı, yerel durum ve uyarılar',deploy_current and deploy.get('scheduled_heartbeat_executed') is True and deploy.get('local_alert_file_verified') is True,'Ben','Dakikalık iş gerçekten çalıştı; dışarıya bildirim gönderildiği iddia edilmez.')
    fee=next((readiness[n] for n in ('category_fee_policy','fee_policy','fee_configuration') if n in readiness),{})
    add('fees','Kategori bazlı ücret politikası',fee.get('passed') is True,'Ben','Politika kontrolü: '+str(fee.get('detail','Kanıt raporu bekleniyor.')))
    checkout=next((readiness[n] for n in ('scoped_finance_evidence','checkout_evidence','finance_checkout_evidence','scoped_checkout_evidence') if n in readiness),{})
    add('checkout','Gerçek checkout toplamı ve kapsam doğrulaması',checkout.get('passed') is True,'Erişim','Ürün sayfası veya ülke navlun tahmini yetmez; SKU/adet/DE/postakodu/vergi/ithalat/toplam gerekir.','access')
    add('order_finance','Çok ürünlü sipariş ve 2 €/adet rezerv',tests_current and (project/'src/finance.py').exists() and (project/'src/automation/engine.py').exists(),'Ben','Ortak ücret bir kez; kuruş koruyan dağıtım ve yeniden işlememe testleri tam suite ile doğrulanır.')
    assets=values['selection'].get('entries',[])
    asset_rows=[a for e in assets for a in e.get('assets',[])]
    asset_files_ok=bool(assets and all(e.get('assets') for e in assets))
    for a in asset_rows:
        try:
            path=(project/a['file']).resolve()
            if not path.is_relative_to((project/'data/product_images').resolve()) or not path.is_file() or path.stat().st_size>12000000:
                asset_files_ok=False;break
            with path.open('rb') as stream:header=stream.read(24)
            if header[:8]!=b'\x89PNG\r\n\x1a\n' or int.from_bytes(header[16:20],'big')!=1600 or int.from_bytes(header[20:24],'big')!=1600:
                asset_files_ok=False;break
        except (OSError,KeyError,TypeError):asset_files_ok=False;break
    add('images','Doğru SKU için gerçek 1600×1600 PNG seti',asset_files_ok,'Ben',f"{len(assets)} ürün / {len(asset_rows)} SKU referanslı görsel; eski 105 görsel yeni ürünlere mal edilmez.")
    add('hosting','Gerçek eBay görsel yükleme ve geri okuma',obs.get('live_image_upload_verified') is True,'Canlı kabul','Adaptör testi gerçek yükleme kanıtı değildir.','live')
    niches=research.get('niche_counts',{})
    add('sourcing','Büro / ev / bahçe araştırması ve taslaklar',all(niches.get(n,0)>0 for n in ('office','home','garden')) and research.get('draft_ready_count',0)>0,'Ben',f"Son doğrulanan araştırma: {research.get('candidate_count',0)} aday, {research.get('draft_ready_count',0)} taslak.")
    candidates=prepared.get('candidates',[])
    ready=[c for c in candidates if c.get('ready_to_publish') is True]
    add('product_profit','Talebi ve kârı doğrulanmış yayıma uygun ürün',bool(ready),'Ben',f"Son adaylar: {len(candidates)}; onaylı: {len(ready)}; ticari eleme: {research.get('commercial_rejection_count',0)}. İlan fiyatı satılmış ürün kanıtı değildir.",'product')
    add('safety','Üretici, AB sorumlusu ve güvenlik bilgileri',any(c.get('provider_facts',{}).get('safety_compliance_verified') is True for c in ready),'Tedarikçi','Adres/e-posta tek başına hukuki üretici adı veya güvenlik belgesi değildir.','external')
    add('rights','Ticari görsel kullanım hakkı',any(c.get('provider_facts',{}).get('image_rights_verified') is True for c in ready),'Tedarikçi','PNG/AI dönüşümü kullanım izni sağlamaz.','external')
    add('supplier_terms','Doğrulanmış tedarik ve gönderim koşulları',passed('supplier_agreement') and bool(ready),'Tedarikçi','Satın alma kabulü tek başına özel tedarik koşullarının teyidi değildir.','external')
    location=values['location']
    add('warehouse','Gerçek depo ile eBay konum eşleşmesi',passed('ebay_locations') and location.get('supplier_dispatch_city_postcode_confirmed') is True,'Tedarikçi / Ben','Son konum incelemesinde iki kayıt da DE; doğrulanmamış CN depo adresi yazılmaz.','external')
    add('email','Gerçek posta hesabı ve takip e-postası okuması',obs.get('mailbox_verified') is True,'Sen / Erişim','mywworkmaill@gmail.com için yetkili bağlantı henüz doğrulanmadı. Şifre/kod bu panelden alınmaz.','access')
    add('payment','Gerçek yetkili ödeme ve bağımsız paid-time doğrulaması',passed('automatic_supplier_payment'),'Sen / Canlı kabul','Kodun varlığı veya Boolean kabul gerçek ödeme kanıtı değildir.','live')
    add('tracking','Gerçek sipariş–ödeme–takip zinciri kabulü',passed('controlled_end_to_end_acceptance'),'Sen / Canlı kabul','İlk gerçek alım gözetimli; gerçek veriyle bağımsız geri okuma gerekir.','live')
    add('commercial','eBay hesabının gerçek ticari statüsü',passed('commercial_account_status'),'Sen','Privat hesabı yapılmış gibi ticari göstermem.','user')
    add('tax','İşletme kaydı ve vergi uygulaması',passed('business_and_tax_setup'),'Sen','2 €/adet yalnız rezervdir, vergi borcu hesaplaması değildir.','user')
    startup=deploy.get('startup',{})
    add('startup','Kalıcı başlangıç kaydı ve onaylı reboot doğrulaması',startup.get('windows_registration_verified') is True and deploy.get('reboot_verified') is True,'Sen / Onay','Kurulum aracı hazır; kalıcı görev ve bilgisayarı yeniden başlatma ayrıca onay gerektirir.','user')
    assert len(rows)==25
    summary=progress_summary(rows)
    watched={'tests':'Tam test raporu güncellendi','deployment':'Servis/yedekleme doğrulaması güncellendi',
             'research':'Niş ürün araştırma sonucu güncellendi','prepared':'İlan taslakları güncellendi',
             'readiness':'Hazırlık engelleri güncellendi','observations':'Gerçek erişim gözlemleri güncellendi','selection':'SKU görsel eşleştirmesi güncellendi'}
    with LOCK:
        for name,label in watched.items():
            path=files[name]
            try:stamp=path.stat().st_mtime_ns
            except OSError:continue
            if SEEN.get(name)!=stamp:
                SEEN[name]=stamp
                EVENTS.append({'at':datetime.fromtimestamp(stamp/1e9,timezone.utc).isoformat(),'message':label})
        EVENTS[:]=sorted(EVENTS,key=lambda e:e['at'])[-30:]
        events=list(reversed(EVENTS))
    if tests_current:doing='Güncel tam test kanıtı var. Kapanmamış kabul ve erişim koşulları aşağıda.'
    else:doing='Son kod için tam test onayı henüz yok; test sözleşmeleri ve birleşik doğrulama bekleniyor.'
    runtime=runtime_status()
    activity,workstreams=workstream_events(project,now)
    stages=stage_tree(rows,values,project,runtime,tests_current,deploy_current,now)
    return dict(summary,stages=stages,activity=activity,workstreams=workstreams,criteria=rows,checked_at=now.isoformat(),target_at='2026-11-06T21:48:13+01:00',
       calculation='25 sabit ve eşit ağırlıklı kabul kontrolü. Geçen / toplam. İş süresi veya kod satırı yüzdesi değildir.',
       doing=doing,source_fingerprint=current,tests_current=tests_current,tests={k:tests.get(k) for k in ('tests_run','failures','errors','skips','passed','generated_at')},
       research={'candidates':research.get('candidate_count',0),'drafts':research.get('draft_ready_count',0),'ready':research.get('publish_ready_count',0),'rejected':research.get('commercial_rejection_count',0)},
       deployment_current=deploy_current,events=events,live_commerce_started=False,runtime=runtime,
       all_complete=summary['verified']==summary['total'],notes=['Yüzde süreye göre artmaz. Yeni kod eski test kanıtını geçersiz kılarsa düşebilir.','Panel bağlı olması otomasyonun veya satışın çalıştığı anlamına gelmez.','Kullanıcı ve dış kanıt koşulları genel yüzdeye dahildir.'])


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Host','').split(':')[0] not in ('127.0.0.1','localhost'):
            self.send_error(403);return
        route=urlsplit(self.path).path
        if route=='/api/status':body=json.dumps(snapshot(),ensure_ascii=False).encode();kind='application/json; charset=utf-8'
        elif route in ('/','/index.html'):body=(HERE/'automation_monitor.html').read_bytes();kind='text/html; charset=utf-8'
        elif route=='/favicon.ico':self.send_response(204);self.end_headers();return
        else:self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
    def do_POST(self):self.send_error(405)
    def log_message(self,format,*args):pass

if __name__=='__main__':
    print('Canlı tamamlanma paneli: http://127.0.0.1:8766',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
