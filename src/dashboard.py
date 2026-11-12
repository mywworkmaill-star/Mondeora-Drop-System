"""
Flask Dashboard - Real-time monitoring and control
"""

from flask import Flask, render_template_string, jsonify, request
from datetime import datetime
from sqlalchemy import func
from html import escape
from pathlib import Path
import secrets
import threading

from src.database.models import get_session, Product, Order, OrderLine, SyncLog
from src.runtime import read_config, PROJECT_ROOT

app = Flask(__name__)
app.config['CONTROL_TOKEN'] = secrets.token_urlsafe(32)
engine = None
_engine_lock = threading.Lock()

def get_engine():
    global engine
    with _engine_lock:
        if engine is None:
            from src.automation.engine import AutamationEngine
            engine = AutamationEngine()
        return engine

@app.before_request
def protect_local_controls():
    if request.host.split(':')[0].lower() not in {'127.0.0.1', 'localhost', '[::1]'}:
        return jsonify(error='Local access only'), 403
    if request.method != 'GET':
        token = request.headers.get('X-Control-Token', '')
        if not secrets.compare_digest(token, app.config['CONTROL_TOKEN']):
            return jsonify(error='Kontrol anahtari gerekli'), 403

@app.after_request
def response_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cache-Control'] = 'no-store'
    return response

HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <title>Mondeora - Dropshipping Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        h1 {
            color: #667eea;
            font-size: 2.5em;
        }
        
        .status-badge {
            padding: 10px 20px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .status-active {
            background: #10b981;
            color: white;
        }
        
        .status-warning {
            background: #f59e0b;
            color: white;
        }
        
        .status-error {
            background: #ef4444;
            color: white;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .card h3 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.1em;
        }
        
        .metric {
            font-size: 2.5em;
            font-weight: bold;
            color: #764ba2;
            margin: 10px 0;
        }
        
        .submetric {
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }
        
        th {
            background: #f3f4f6;
            font-weight: 600;
            color: #667eea;
        }
        
        tr:hover {
            background: #f9fafb;
        }
        
        .action-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9em;
            margin: 5px;
            transition: all 0.3s ease;
        }
        
        .action-btn:hover {
            background: #764ba2;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .action-btn.secondary {
            background: #e5e7eb;
            color: #333;
        }
        
        .action-btn.secondary:hover {
            background: #d1d5db;
        }
        
        .action-btn.danger {
            background: #ef4444;
        }
        
        .action-btn.danger:hover {
            background: #dc2626;
        }
        
        .update-time {
            color: #999;
            font-size: 0.9em;
            margin-top: 15px;
            text-align: right;
        }
        
        .product-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
        }
        
        .badge-active {
            background: #d1fae5;
            color: #065f46;
        }
        
        .badge-paused {
            background: #fef3c7;
            color: #92400e;
        }
        
        .badge-error {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .chart-container {
            margin-top: 20px;
            padding: 20px;
            background: #f9fafb;
            border-radius: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>🚀 Mondeora Dropshipping</h1>
                <p>Real-time Automation & Control Panel</p>
            </div>
            <div class="status-badge status-active" id="system-status">KONTROL EDILIYOR</div>
        </header>
        
        <!-- Key Metrics -->
        <div class="grid">
            <div class="card">
                <h3>📊 Listed Products</h3>
                <div class="metric" id="metric-products">0</div>
                <div class="submetric" id="metric-products-active">0 active</div>
            </div>
            
            <div class="card">
                <h3>📦 Total Orders</h3>
                <div class="metric" id="metric-orders">0</div>
                <div class="submetric" id="metric-orders-processed">0 processed today</div>
            </div>
            
            <div class="card">
                <h3>💰 Revenue Today</h3>
                <div class="metric" id="metric-revenue">€0.00</div>
                <div class="submetric" id="metric-profit">€0 profit</div>
            </div>
            
            <div class="card">
                <h3>📈 Conversion Rate</h3>
                <div class="metric" id="metric-conversion">0%</div>
                <div class="submetric">Average across all products</div>
            </div>
        </div>
        
        <!-- Control Panel -->
        <div class="card">
            <h3>🎛️ Control Panel</h3>
            <button class="action-btn" onclick="syncProducts()">Sync Products Now</button>
            <button class="action-btn" onclick="syncOrders()">Check Orders Now</button>
            <button class="action-btn" onclick="syncInventory()">Sync Inventory Now</button>
            <button class="action-btn" onclick="optimizePrices()">Optimize Prices Now</button>
            <button class="action-btn secondary" onclick="viewLogs()">View Logs</button>
        </div>
        
        <div class="card">
            <h3>Otomatik Urun Arastirmasi</h3>
            <p>Urun kimligi girmeden aday arastirma; eksik veriyle ilan veya satin alma yapilmaz.</p>
            <button class="action-btn" onclick="fetch('/api/sync/research', {method:'POST'}).then(r=>r.json()).then(data=>alert(JSON.stringify(data)))">Urunleri Otomatik Arastir</button>
            <a href="/api/research" target="_blank" rel="noopener">Adaylar ve engeller raporu</a>
            <a href="/preparation" target="_blank" rel="noopener">Ürün hazırlığı, Almanca taslaklar ve eksik kanıtlar</a>
        </div>
        <!-- Recent Products -->
        <div class="card" style="margin-top: 30px;">
            <h3>🏷️ Recent Products</h3>
            <table id="products-table">
                <thead>
                    <tr>
                        <th>Title</th>
                        <th>Price (€)</th>
                        <th>Stock</th>
                        <th>Margin</th>
                        <th>Status</th>
                        <th>Sales</th>
                    </tr>
                </thead>
                <tbody id="products-tbody">
                    <tr>
                        <td colspan="6" style="text-align: center; color: #999;">Loading...</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <!-- Recent Orders -->
        <div class="card" style="margin-top: 30px;">
            <h3>📮 Recent Orders</h3>
            <table id="orders-table">
                <thead>
                    <tr>
                        <th>Order ID</th>
                        <th>Product</th>
                        <th>Amount (€)</th>
                        <th>Status</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody id="orders-tbody">
                    <tr>
                        <td colspan="5" style="text-align: center; color: #999;">Loading...</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <div class="update-time">
            Last updated: <span id="last-update">Just now</span>
        </div>
    </div>
    
    <script>
        const controlToken = {{ control_token|tojson }};
        const originalFetch = window.fetch.bind(window);
        window.fetch = async function(url, options = {}) {
            if (options.method && options.method !== 'GET') {
                options.headers = {...(options.headers || {}), 'X-Control-Token': controlToken};
            }
            const response = await originalFetch(url, options);
            if (!response.ok) {
                let data = await response.json().catch(() => ({}));
                throw new Error(data.error || data.message || data.status || 'Islem basarisiz');
            }
            return response;
        };
        window.addEventListener('unhandledrejection', event => {
            alert(event.reason?.message || 'Baglanti hatasi');
        });
        function escapeHTML(value) {
            const element = document.createElement('span');
            element.textContent = String(value ?? '');
            return element.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }
        function updateHealth() {
            fetch('/api/health').then(r => r.json()).then(data => {
                const badge = document.getElementById('system-status');
                badge.textContent = JSON.stringify(data);
                badge.className = 'status-badge status-warning';
            });
        }
        function updateMetrics() {
            fetch('/api/metrics')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('metric-products').textContent = data.total_products;
                    document.getElementById('metric-products-active').textContent = data.active_products + ' active';
                    document.getElementById('metric-orders').textContent = data.total_orders;
                    document.getElementById('metric-orders-processed').textContent = data.orders_today + ' processed today';
                    document.getElementById('metric-revenue').textContent = '€' + data.revenue_today.toFixed(2);
                    document.getElementById('metric-profit').textContent = '€' + data.profit_today.toFixed(2) + ' profit';
                    document.getElementById('metric-conversion').textContent = data.conversion_rate.toFixed(1) + '%';
                    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                });
        }
        
        function loadProducts() {
            fetch('/api/products')
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('products-tbody');
                    tbody.innerHTML = '';
                    data.products.slice(0, 10).forEach(p => {
                        tbody.innerHTML += `
                            <tr>
                                <td>${escapeHTML(p.title.substring(0, 40))}...</td>
                                <td>€${p.ebay_price.toFixed(2)}</td>
                                <td>${p.current_stock}</td>
                                <td>${p.margin_percent.toFixed(1)}%</td>
                                <td><span class="product-badge badge-${escapeHTML(p.status)}">${escapeHTML(p.status.toUpperCase())}</span></td>
                                <td>${p.sales}</td>
                            </tr>
                        `;
                    });
                });
        }
        
        function loadOrders() {
            fetch('/api/orders')
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('orders-tbody');
                    tbody.innerHTML = '';
                    data.orders.slice(0, 10).forEach(o => {
                        tbody.innerHTML += `
                            <tr>
                                <td>${escapeHTML(o.ebay_order_id)}</td>
                                <td>${escapeHTML(o.product_title.substring(0, 30))}...</td>
                                <td>€${o.total_amount.toFixed(2)}</td>
                                <td><span class="product-badge badge-active">${escapeHTML(o.order_status)}</span></td>
                                <td>${new Date(o.order_date).toLocaleDateString()}</td>
                            </tr>
                        `;
                    });
                });
        }
        
        function syncProducts() {
            if(confirm('Start product sync now?')) {
                fetch('/api/sync/products', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        alert(`✅ Sync complete: ${data.processed} products processed`);
                        updateMetrics();
                        loadProducts();
                    });
            }
        }
        
        function syncOrders() {
            if(confirm('Start order sync now?')) {
                fetch('/api/sync/orders', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        alert(`✅ Sync complete: ${data.processed} orders processed`);
                        updateMetrics();
                        loadOrders();
                    });
            }
        }
        
        function syncInventory() {
            if(confirm('Start inventory sync now?')) {
                fetch('/api/sync/inventory', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        alert(`✅ Sync complete: ${data.synced} products updated`);
                        loadProducts();
                    });
            }
        }
        
        function optimizePrices() {
            if(confirm('Start price optimization now?')) {
                fetch('/api/sync/prices', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        alert(`✅ Optimization complete: ${data.optimized} products updated`);
                        loadProducts();
                    });
            }
        }
        
        function viewLogs() {
            window.open('/logs', '_blank');
        }
        
        // Initial load
        updateHealth();
        setInterval(updateHealth, 30000);
        updateMetrics();
        loadProducts();
        loadOrders();
        
        // Refresh every 30 seconds
        setInterval(updateMetrics, 30000);
        setInterval(loadProducts, 60000);
        setInterval(loadOrders, 60000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_DASHBOARD, control_token=app.config['CONTROL_TOKEN'])

@app.route('/api/health')
def health():
    runtime = get_engine()
    state = runtime.status()
    operations = getattr(runtime, 'operations', None)
    state['operations'] = operations.status() if operations else {'status': 'not_started'}
    return jsonify(state)

@app.route('/api/research')
def get_research():
    path = PROJECT_ROOT / 'data/product_research.json'
    if not path.exists():
        return jsonify(status='not_run', candidates=[])
    import json
    try:
        return jsonify(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, ValueError):
        return jsonify(error='Arastirma raporu okunamadi'), 503

@app.route('/api/preparation')
def get_preparation():
    import json
    path = PROJECT_ROOT / 'data/product_preparation.json'
    try:
        return jsonify(json.loads(path.read_text(encoding='utf-8')))
    except FileNotFoundError:
        return jsonify(status='not_run', candidates=[])
    except (OSError, ValueError):
        return jsonify(error='Urun hazirlik raporu okunamadi'), 503


@app.route('/preparation')
def preparation_page():
    response = get_preparation()
    if isinstance(response, tuple):
        return response
    report = response.get_json()
    return render_template_string('''<!doctype html><html lang="tr"><meta charset="utf-8">
        <meta http-equiv="refresh" content="30"><title>Mondeora Ürün Hazırlığı</title>
        <style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;background:#f4f6fa}article{padding:1rem;background:white;margin:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}li{margin:.3rem}</style>
        <h1>Ürün hazırlığı — salt okunur</h1><p>Taslak, satış veya yayın onayı değildir.</p>
        <p>Güncelleme: {{ report.get('generated_at','Henüz çalıştırılmadı') }} · Aday: {{ report.get('candidate_count',0) }} · Taslak: {{ report.get('draft_ready_count',0) }} · Yayına hazır: {{ report.get('publish_ready_count',0) }}</p>
        <a href="/api/preparation">JSON ve kanıt/tedarikçi görevleri</a>
        {% for item in report.get('candidates',[]) %}<article><h2>{{ item.title }}</h2>
        <p>Ürün {{ item.product_id }} / SKU {{ item.sku_id or item.get('requested_sku_id') }} — {{ item.preparation_state }}</p>
        <h3>Eksik doğrulamalar</h3><ul>{% for blocker in item.blockers %}<li>{{ blocker }}</li>{% endfor %}</ul>
        {% if item.listing_draft %}<h3>Almanca taslak: {{ item.listing_draft.title }}</h3>
        <pre>{{ item.listing_draft.description_html }}</pre>{% endif %}
        <p>Kaynak maliyet: {{ item.get('source_cost_eur') }} EUR · Ülke navlun tahmini: {{ item.get('shipping_cost_eur') }} EUR · Bilinmeyen ithalat hariç fiyat tabanı: {{ item.get('price_floor_eur') }} EUR</p>
        </article>{% endfor %}</html>''', report=report)


@app.route('/api/metrics')
def get_metrics():
    with get_session(get_engine().engine) as session:
        today = datetime.combine(datetime.utcnow().date(), datetime.min.time())
        totals = session.query(func.sum(Order.total_amount), func.sum(Order.profit_amount), func.count(Order.id)).filter(Order.order_date >= today).one()
        views = session.query(func.sum(Product.views)).scalar() or 0
        sales = session.query(func.sum(Order.quantity)).scalar() or 0
        return jsonify(total_products=session.query(Product).count(),
            active_products=session.query(Product).filter_by(is_listed=True).count(),
            total_orders=session.query(Order).count(), orders_today=totals[2],
            revenue_today=float(totals[0] or 0), profit_today=float(totals[1] or 0),
            conversion_rate=(sales / views * 100) if views else 0)

@app.route('/api/products')
def get_products():
    with get_session(get_engine().engine) as session:
        products = session.query(Product).order_by(Product.updated_at.desc()).limit(50).all()
        return jsonify(products=[dict(id=p.id, title=p.title or '', ebay_price=p.ebay_price or 0,
            current_stock=p.current_stock, margin_percent=p.margin_percent or 0,
            status=p.status or 'unknown', sales=p.sales or 0, verified=bool(p.fulfillment_verified)) for p in products])

@app.route('/api/orders')
def get_orders():
    with get_session(get_engine().engine) as session:
        rows = session.query(Order, Product.title).outerjoin(Product, Product.ebay_item_id == Order.ebay_item_id).order_by(Order.order_date.desc()).limit(50).all()
        return jsonify(orders=[dict(ebay_order_id=o.ebay_order_id, product_title=title or 'Bilinmiyor',
            total_amount=o.total_amount or 0, order_status=o.order_status or 'unknown',
            order_date=o.order_date.isoformat() if o.order_date else None) for o, title in rows])

@app.route('/api/sync/<operation>', methods=['POST'])
def run_operation(operation):
    actions = {'research': 'research_products', 'products': 'sync_top_products_from_aliexpress', 'orders': 'sync_ebay_orders_and_place_aliexpress_orders',
        'inventory': 'sync_inventory', 'prices': 'analyze_competition_and_optimize_prices'}
    if operation not in actions:
        return jsonify(error='Unknown operation'), 404
    result = getattr(get_engine(), actions[operation])()
    code = 409 if result.get('status') in {'blocked', 'skipped', 'failed', 'partial'} else 200
    return jsonify(result), code

@app.route('/logs')
def show_logs():
    # Legacy log files may contain credentials or buyer data: never serve raw logs.
    with get_session(get_engine().engine) as session:
        rows = session.query(SyncLog).order_by(SyncLog.id.desc()).limit(50).all()
        return jsonify(events=[dict(type=r.sync_type, status=r.status,
            processed=r.processed_items, failed=r.failed_items,
            time=r.started_at.isoformat() if r.started_at else None) for r in rows])

if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=5000)
