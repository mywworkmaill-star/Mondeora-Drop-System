"""Loopback finance journal and scenario UI; no marketplace mutation APIs."""
import csv
from decimal import Decimal
from io import StringIO
import json
from pathlib import Path
import secrets
from flask import Flask,request,jsonify,Response,send_file
from src.runtime import PROJECT_ROOT
from src.finance import open_ledger,append_sale,reserve_rows as ledger_rows,plan_order


def create_app(data_dir=None,control_token=None):
    root=Path(data_dir or PROJECT_ROOT/'data/finance')
    root.mkdir(parents=True,exist_ok=True)
    db=root/'finance_ledger.sqlite3'
    open_ledger(db)
    app=Flask(__name__)
    app.config['MAX_CONTENT_LENGTH']=65536
    token=control_token or secrets.token_urlsafe(32)
    @app.before_request
    def protect():
        if request.host.split(':')[0] not in {'localhost','127.0.0.1'}: return jsonify(error='Local host required'),403
        if request.method=='POST':
            if not secrets.compare_digest(request.headers.get('X-Finance-Control',''),token): return jsonify(error='Control token required'),403
            origin=request.headers.get('Origin')
            if origin and origin not in {'http://127.0.0.1:8767','http://localhost:8767'}: return jsonify(error='Origin rejected'),403
    @app.after_request
    def headers(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response
    @app.get('/')
    def index():
        path=root/'index.html'
        if not path.exists(): return 'Finance UI not built',503
        return Response(path.read_text(encoding='utf-8').replace('__FINANCE_TOKEN__',token),mimetype='text/html')
    @app.get('/api/overview')
    def overview():
        plan_path=root/'product_plan.json'
        plan=json.loads(plan_path.read_text(encoding='utf-8')) if plan_path.exists() else {'products':[]}
        rows=ledger_rows(db)
        return jsonify(plan=plan,actual_orders=rows,summary={
          'orders':len(rows),'units':sum(r['quantity'] for r in rows),
          'tax_reserve':str(sum((Decimal(r['tax_reserve']) for r in rows),Decimal('0'))),
          'incomplete_cost_orders':sum(not r['costs_complete'] for r in rows),
          'tax_liability':None})
    @app.post('/api/quote')
    def quote():
        try:
            payload=request.get_json(silent=True) or {}
            result=plan_order(payload['buyer_gross'],payload['unit_source'],payload['shipping_total'],payload['category_root'],
                quantity=payload.get('quantity',1),additional_import_cost=payload.get('additional_import_cost'),
                marketplace_vat_percent=payload.get('marketplace_vat_percent','19'),fee_vat_percent=payload.get('fee_vat_percent','19'))
            return jsonify(json.loads(json.dumps(result,default=str)))
        except (KeyError,ValueError,TypeError): return jsonify(error='Geçerli EUR tutarları ve desteklenen kategori gerekli.'),400
    @app.post('/api/sales')
    def sales():
        try: return jsonify(append_sale(db,request.get_json(silent=True))),201
        except (ValueError,TypeError) as error: return jsonify(error=str(error)),400
    @app.get('/export.json')
    def export_json():
        return jsonify(schema='mondeora-finance-v1',tax_reserve_per_unit_eur='2.00',actual_orders=ledger_rows(db))
    @app.get('/export.csv')
    def export_csv():
        rows=ledger_rows(db)
        fields=['order_id','paid_date','product','quantity','buyer_gross','marketplace_vat','ebay_fees_actual','source_total',
                'shipping_total','import_total','other_total','tax_reserve','known_surplus_after_reserve','net_after_reserve','costs_complete','created_at']
        output=StringIO();writer=csv.DictWriter(output,fieldnames=fields,delimiter=';',extrasaction='ignore');writer.writeheader()
        for row in rows:
            sanitized={k: ("'"+v if isinstance(v,str) and v.startswith(('=','+','@')) else v) for k,v in row.items()}
            writer.writerow(sanitized)
        return Response('\ufeff'+output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=Mondeora_Gercek_Islemler.csv'})
    @app.get('/download.xlsx')
    def excel():
        path=root/'Mondeora_Finans_Takibi.xlsx'
        if not path.exists(): return 'Workbook not built',404
        return send_file(path,as_attachment=True)
    return app


if __name__=='__main__':
    print('Finance: http://127.0.0.1:8767',flush=True)
    create_app().run(host='127.0.0.1',port=8767,debug=False,use_reloader=False)
