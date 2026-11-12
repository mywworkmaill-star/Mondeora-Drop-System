"""
Database Models - Mondeora Dropshipping System
Complete database schema for products, orders, and sync tracking
"""

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Boolean, Text, UniqueConstraint, inspect, text, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import make_url
from datetime import datetime
from pathlib import Path
import os
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]
Base = declarative_base()
DATABASE_URL = dotenv_values(PROJECT_ROOT / '.env').get('DATABASE_URL') or 'sqlite:///' + (PROJECT_ROOT / 'data/dropshipping.db').as_posix()


class Product(Base):
    """AliExpress products synced to eBay"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True)
    aliexpress_product_id = Column(String(50), unique=True, index=True)
    ebay_item_id = Column(String(50), unique=True, nullable=True, index=True)
    sku_id = Column(String(100), nullable=True)
    ebay_offer_id = Column(String(100), nullable=True)
    shipping_cost = Column(Float, nullable=True)
    currency = Column(String(3), default='EUR')
    category_id = Column(String(50), nullable=True)
    # Existing records are NOT automatically approved for listing or purchasing.
    fulfillment_verified = Column(Boolean, default=False, nullable=False)
    
    title = Column(String(500))
    description = Column(Text)
    category = Column(String(100))
    image_url = Column(Text)
    
    # Pricing
    aliexpress_price = Column(Float)  # Source price
    ebay_price = Column(Float)  # Selling price
    margin_percent = Column(Float)  # Profit margin %
    
    # Stock
    aliexpress_stock = Column(Integer)
    current_stock = Column(Integer)
    
    # Status
    status = Column(String(50), default="active")  # active, paused, sold_out, error
    is_listed = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_synced = Column(DateTime)
    
    # Performance
    views = Column(Integer, default=0)
    sales = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)
    

class Order(Base):
    """Orders from eBay"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True)
    ebay_order_id = Column(String(50), unique=True, index=True)
    ebay_item_id = Column(String(50), index=True)
    aliexpress_product_id = Column(String(50))
    
    # Customer info
    buyer_email = Column(String(200))
    shipping_address = Column(Text)
    
    # Order details
    quantity = Column(Integer)
    ebay_price = Column(Float)
    total_amount = Column(Float)
    profit_amount = Column(Float)
    
    # Status
    order_status = Column(String(50), default="received")  # received, processing, shipped, delivered, cancelled
    aliexpress_order_id = Column(String(50), nullable=True)
    
    # Timestamps
    order_date = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    shipped_date = Column(DateTime, nullable=True)
    delivered_date = Column(DateTime, nullable=True)
    

class SyncLog(Base):
    """Sync history for debugging and monitoring"""
    __tablename__ = "sync_logs"
    
    id = Column(Integer, primary_key=True)
    sync_type = Column(String(50))  # "product_sync", "order_sync", "inventory_sync"
    
    status = Column(String(50))  # "success", "failed", "partial"
    total_items = Column(Integer)
    processed_items = Column(Integer)
    failed_items = Column(Integer)
    
    error_message = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float)
    

class PriceHistory(Base):
    """Track price changes for analytics"""
    __tablename__ = "price_history"
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, index=True)
    ebay_item_id = Column(String(50))
    
    aliexpress_price = Column(Float)
    ebay_price = Column(Float)
    margin_percent = Column(Float)
    
    reason = Column(String(100))  # "manual_update", "stock_low", "competitor_adjustment"
    
    recorded_at = Column(DateTime, default=datetime.utcnow)


class CompetitorAnalysis(Base):
    """Track competitor prices for market intelligence"""
    __tablename__ = "competitor_analysis"
    
    id = Column(Integer, primary_key=True)
    product_category = Column(String(100))
    competitor_id = Column(String(100))
    competitor_url = Column(Text)
    
    product_title = Column(String(500))
    competitor_price = Column(Float)
    our_price = Column(Float)
    price_difference = Column(Float)
    
    analyzed_at = Column(DateTime, default=datetime.utcnow)


class SystemSettings(Base):
    """Configuration settings"""
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True)
    setting_key = Column(String(100), unique=True)
    setting_value = Column(Text)
    data_type = Column(String(50))  # "string", "integer", "float", "boolean"
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrderLine(Base):
    """Durable per-line reservation: ambiguous purchases require reconciliation."""
    __tablename__ = 'order_lines'
    __table_args__ = (UniqueConstraint('ebay_order_id', 'ebay_line_item_id', name='uq_order_line'),)
    id = Column(Integer, primary_key=True)
    ebay_order_id = Column(String(100), nullable=False, index=True)
    ebay_line_item_id = Column(String(100), nullable=False)
    product_id = Column(Integer, nullable=True)
    aliexpress_order_id = Column(String(100), nullable=True)
    external_order_id = Column(String(160), unique=True, nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, default='staged')
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_database(url=None):
    """Create missing tables and apply additive migrations; never replace user data."""
    db_url = make_url(url or DATABASE_URL)
    if db_url.drivername.startswith('sqlite') and db_url.database not in (None, '', ':memory:'):
        path = Path(db_url.database)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        db_url = db_url.set(database=str(path))
    options = {'connect_args': {'timeout': 30, 'check_same_thread': False}} if db_url.drivername.startswith('sqlite') else {}
    engine = create_engine(db_url, echo=False, pool_pre_ping=True, **options)
    if db_url.drivername.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def set_sqlite_options(connection, _record):
            cursor = connection.cursor()
            cursor.execute('PRAGMA busy_timeout=30000')
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()
    Base.metadata.create_all(engine)
    columns = {c['name'] for c in inspect(engine).get_columns('products')}
    additions = {
        'sku_id': 'VARCHAR(100)', 'ebay_offer_id': 'VARCHAR(100)',
        'shipping_cost': 'FLOAT', 'currency': "VARCHAR(3) DEFAULT 'EUR'",
        'category_id': 'VARCHAR(50)', 'fulfillment_verified': 'BOOLEAN NOT NULL DEFAULT 0',
    }
    with engine.begin() as connection:
        for name, declaration in additions.items():
            if name not in columns:
                connection.execute(text(f'ALTER TABLE products ADD COLUMN {name} {declaration}'))
    return engine


def get_session(engine):
    """Get database session"""
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == "__main__":
    engine = init_database()
    print("✅ Database initialized successfully")
    print(f"📁 Database: {DATABASE_URL}")
