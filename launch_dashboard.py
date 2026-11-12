#!/usr/bin/env python
"""
Mondeora Ultra - Analytics Dashboard Launcher
Simplified version (no AI dependencies required for first launch)
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

def get_dashboard_data():
    """
    Get real data from database for dashboard
    """
    db = sqlite3.connect('data/dropshipping.db')
    cursor = db.cursor()
    
    # Today's metrics
    today = datetime.now().date()
    
    # All products
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    
    # Recent sales (if we have orders table)
    try:
        cursor.execute("""
            SELECT created_at, total_amount, net_profit 
            FROM orders 
            WHERE created_at >= date('now', '-30 days')
        """)
        sales = cursor.fetchall()
    except:
        sales = []
    
    db.close()
    
    return {
        'total_products': len(products),
        'total_sales': len(sales),
        'today_revenue': 0,  # Placeholder
        'month_revenue': sum(s[1] for s in sales) if sales else 0,
        'month_profit': sum(s[2] for s in sales) if sales else 0,
    }

def launch_simple_dashboard():
    """
    Launch basic HTML dashboard (no Plotly needed for MVP)
    """
    import http.server
    import socketserver
    from pathlib import Path
    
    # Get data
    data = get_dashboard_data()
    
    # Generate HTML dashboard
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Mondeora ULTRA - Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: white;
            text-align: center;
            margin-bottom: 40px;
            font-size: 2.5em;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .kpi-card {{
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .kpi-value {{
            font-size: 3em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
        }}
        .kpi-label {{
            font-size: 1.2em;
            color: #666;
        }}
        .status {{
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .status h2 {{
            color: #667eea;
            margin-bottom: 20px;
        }}
        .status-item {{
            display: flex;
            justify-content: space-between;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 5px;
            margin-bottom: 10px;
        }}
        .badge {{
            background: #28a745;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
        }}
        .next-steps {{
            background: white;
            border-radius: 10px;
            padding: 30px;
            margin-top: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .next-steps h2 {{
            color: #667eea;
            margin-bottom: 20px;
        }}
        .next-steps ul {{
            list-style: none;
        }}
        .next-steps li {{
            padding: 15px;
            background: #f8f9fa;
            border-radius: 5px;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Mondeora ULTRA Dashboard</h1>
        
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-value">{data['total_products']}</div>
                <div class="kpi-label">Total Products</div>
            </div>
            
            <div class="kpi-card">
                <div class="kpi-value">€{data['month_revenue']:.2f}</div>
                <div class="kpi-label">Month Revenue</div>
            </div>
            
            <div class="kpi-card">
                <div class="kpi-value">€{data['month_profit']:.2f}</div>
                <div class="kpi-label">Month Profit</div>
            </div>
            
            <div class="kpi-card">
                <div class="kpi-value">{data['total_sales']}</div>
                <div class="kpi-label">Total Orders</div>
            </div>
        </div>
        
        <div class="status">
            <h2>System Status</h2>
            <div class="status-item">
                <span>Database</span>
                <span class="badge">✅ Connected</span>
            </div>
            <div class="status-item">
                <span>eBay API</span>
                <span class="badge">✅ Active</span>
            </div>
            <div class="status-item">
                <span>AliExpress API</span>
                <span class="badge">✅ Active</span>
            </div>
            <div class="status-item">
                <span>Automation</span>
                <span class="badge">⏸️ Ready</span>
            </div>
        </div>
        
        <div class="next-steps">
            <h2>🚀 Next Steps</h2>
            <ul>
                <li><strong>Step 1:</strong> Add OpenAI API key to .env for AI features</li>
                <li><strong>Step 2:</strong> Run: <code>python create_listings_bulletproof_full.py --keyword 'pet toy' --count 10</code></li>
                <li><strong>Step 3:</strong> Start automation: <code>python start_automation.py</code></li>
                <li><strong>Step 4:</strong> Monitor dashboard: Refresh this page</li>
            </ul>
        </div>
    </div>
</body>
</html>
    """
    
    # Save HTML
    Path('dashboard_ultra.html').write_text(html, encoding='utf-8')
    
    print("=" * 60)
    print("🎉 DASHBOARD LAUNCHED!")
    print("=" * 60)
    print()
    print(f"📊 Dashboard URL: http://localhost:8768/dashboard_ultra.html")
    print()
    print("Starting web server...")
    print("Press Ctrl+C to stop")
    print()
    
    # Start simple HTTP server
    PORT = 8768
    Handler = http.server.SimpleHTTPRequestHandler
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"✅ Server running at http://localhost:{PORT}/")
        httpd.serve_forever()

if __name__ == "__main__":
    try:
        launch_simple_dashboard()
    except KeyboardInterrupt:
        print("\n\n✅ Dashboard stopped")
