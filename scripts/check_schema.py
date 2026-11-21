#!/usr/bin/env python3
"""Check database schema"""

import sqlite3

conn = sqlite3.connect('data/dropshipping.db')
c = conn.cursor()

# Check products table schema
c.execute("PRAGMA table_info(products)")
print("PRODUCTS TABLE SCHEMA:")
for row in c.fetchall():
    print(f"  {row}")

# Check sales table schema
c.execute("PRAGMA table_info(sales)")
print("\nSALES TABLE SCHEMA:")
for row in c.fetchall():
    print(f"  {row}")

# Check if sales table exists and has data
c.execute("SELECT COUNT(*) FROM sales")
count = c.fetchone()[0]
print(f"\nTotal rows in sales: {count}")

if count > 0:
    c.execute("SELECT * FROM sales LIMIT 1")
    print(f"\nSample row columns: {[desc[0] for desc in c.description]}")

conn.close()
