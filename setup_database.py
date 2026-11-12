#!/usr/bin/env python3
"""
Veritabanını kur
"""

import sys
import os

# Path ekle
sys.path.insert(0, os.path.dirname(__file__))

print("\n" + "╔" + "="*60 + "╗")
print("║ 🗄️  VERİTABANI OLUŞTURULUYOR                                 ║")
print("╚" + "="*60 + "╝")

# SQLAlchemy kur
print("\n1️⃣  Gerekli paketler kontrol ediliyor...")

try:
    import sqlalchemy
    print(f"   ✅ SQLAlchemy: {sqlalchemy.__version__}")
except ImportError:
    print("   ⚠️  SQLAlchemy kuruluyor...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "sqlalchemy"], check=True)
    import sqlalchemy
    print(f"   ✅ SQLAlchemy: {sqlalchemy.__version__}")

# Veritabanını oluştur
print("\n2️⃣  Veritabanı oluşturuluyor...")

try:
    os.environ['DATABASE_URL'] = 'sqlite:///./data/dropshipping.db'
    
    from src.database.models import Base, engine
    
    Base.metadata.create_all(bind=engine)
    print("   ✅ Tablolar oluşturuldu!")
    
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print(f"\n3️⃣  Tablolar ({len(tables)}):")
    for table in sorted(tables):
        columns = inspector.get_columns(table)
        print(f"   ✅ {table:20} ({len(columns):2} sütun)")
    
    print(f"\n   ✅ VERİTABANI HAZIR!")
    
except Exception as e:
    print(f"   ❌ Hata: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
