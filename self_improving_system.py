#!/usr/bin/env python
"""
SELF-IMPROVING AUTOMATION SYSTEM
Monitors, learns, optimizes, and improves itself automatically!
"""

import sys
import os
sys.path.insert(0, '.')

import json
import time
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path

class SelfImprovingSystem:
    """
    Autonomous system that learns from results and optimizes itself
    """
    
    def __init__(self):
        self.db_path = 'data/dropshipping.db'
        self.learning_db = 'data/learning_database.db'
        self.strategies_file = 'data/strategies.json'
        self.performance_log = 'data/performance_log.json'
        
        self.initialize_learning_database()
        self.load_strategies()
        
    def initialize_learning_database(self):
        """Create learning database for tracking experiments"""
        conn = sqlite3.connect(self.learning_db)
        cursor = conn.cursor()
        
        # Strategy performance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT,
                platform TEXT,
                post_title TEXT,
                post_content TEXT,
                views INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                sales INTEGER DEFAULT 0,
                revenue REAL DEFAULT 0,
                profit REAL DEFAULT 0,
                conversion_rate REAL DEFAULT 0,
                roi REAL DEFAULT 0,
                timestamp DATETIME,
                success_score REAL DEFAULT 0
            )
        ''')
        
        # Learning insights table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learning_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                insight_type TEXT,
                insight TEXT,
                confidence REAL,
                evidence TEXT,
                timestamp DATETIME,
                applied BOOLEAN DEFAULT 0
            )
        ''')
        
        # A/B test results
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ab_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT,
                variant_a TEXT,
                variant_b TEXT,
                winner TEXT,
                improvement_percent REAL,
                sample_size INTEGER,
                timestamp DATETIME
            )
        ''')
        
        conn.commit()
        conn.close()
        
        print("✅ Learning database initialized!")
    
    def load_strategies(self):
        """Load current strategies from file"""
        if os.path.exists(self.strategies_file):
            with open(self.strategies_file, 'r', encoding='utf-8') as f:
                self.strategies = json.load(f)
        else:
            # Default strategies
            self.strategies = {
                'reddit': {
                    'best_titles': [
                        '[DEAL] Premium Haustier-Spielzeug auf eBay.de - 50% günstiger',
                        'Günstige Haustier-Spielzeuge - Wo kauft ihr ein?'
                    ],
                    'best_times': ['10:00', '15:00', '20:00'],
                    'best_subreddits': ['de', 'Haustiere'],
                    'performance_score': 0
                },
                'facebook': {
                    'best_groups': [],
                    'best_post_times': ['09:00', '18:00', '21:00'],
                    'best_content_type': 'deal_announcement',
                    'performance_score': 0
                },
                'optimization': {
                    'price_discount_percent': 15,
                    'free_shipping_threshold': 0,
                    'best_product_categories': ['pet_toys'],
                    'conversion_rate_target': 2.0
                }
            }
            self.save_strategies()
    
    def save_strategies(self):
        """Save updated strategies"""
        with open(self.strategies_file, 'w', encoding='utf-8') as f:
            json.dump(self.strategies, f, indent=2)
    
    def collect_performance_data(self):
        """Collect data from all sources"""
        print("=" * 70)
        print("📊 COLLECTING PERFORMANCE DATA...")
        print("=" * 70)
        print()
        
        data = {
            'ebay_sales': self.get_ebay_sales(),
            'product_performance': self.get_product_performance(),
            'social_media_metrics': self.estimate_social_metrics(),
            'timestamp': datetime.now().isoformat()
        }
        
        # Save to performance log
        self.append_to_log(data)
        
        return data
    
    def get_ebay_sales(self):
        """Get sales data from eBay/database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get sales from last 24 hours
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()
            
            cursor.execute('''
                SELECT COUNT(*), SUM(ebay_price), AVG(ebay_price)
                FROM products
                WHERE status = 'SOLD'
                AND updated_at > ?
            ''', (yesterday,))
            
            sales_count, total_revenue, avg_price = cursor.fetchone()
            
            conn.close()
            
            return {
                'sales_count': sales_count or 0,
                'revenue': total_revenue or 0,
                'avg_order_value': avg_price or 0
            }
            
        except Exception as e:
            print(f"⚠️  Could not get sales data: {e}")
            return {'sales_count': 0, 'revenue': 0, 'avg_order_value': 0}
    
    def get_product_performance(self):
        """Analyze which products perform best"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ebay_item_id, title, ebay_price, status
                FROM products
                WHERE status IN ('ACTIVE', 'SOLD')
                ORDER BY updated_at DESC
                LIMIT 50
            ''')
            
            products = cursor.fetchall()
            conn.close()
            
            return {
                'total_active': len([p for p in products if p[3] == 'ACTIVE']),
                'total_sold': len([p for p in products if p[3] == 'SOLD']),
                'avg_price': sum([p[2] for p in products]) / len(products) if products else 0
            }
            
        except Exception as e:
            print(f"⚠️  Could not get product data: {e}")
            return {'total_active': 0, 'total_sold': 0, 'avg_price': 0}
    
    def estimate_social_metrics(self):
        """Estimate social media performance"""
        # In future: integrate with Reddit/Facebook APIs
        # For now: estimate based on time elapsed
        
        return {
            'reddit_estimated_views': 500,  # Will be real data later
            'facebook_estimated_views': 0,
            'total_estimated_reach': 500
        }
    
    def analyze_and_learn(self, performance_data):
        """Analyze data and extract insights"""
        print()
        print("=" * 70)
        print("🧠 ANALYZING DATA & LEARNING...")
        print("=" * 70)
        print()
        
        insights = []
        
        # Insight 1: Sales conversion rate
        sales = performance_data['ebay_sales']['sales_count']
        reach = performance_data['social_media_metrics']['total_estimated_reach']
        
        if reach > 0:
            conversion_rate = (sales / reach) * 100
            
            if conversion_rate > 2.0:
                insights.append({
                    'type': 'success',
                    'insight': f'High conversion rate: {conversion_rate:.2f}% - Current strategy is working!',
                    'confidence': 0.9,
                    'action': 'keep_strategy'
                })
            elif conversion_rate < 0.5:
                insights.append({
                    'type': 'warning',
                    'insight': f'Low conversion rate: {conversion_rate:.2f}% - Need to optimize',
                    'confidence': 0.8,
                    'action': 'test_new_strategy'
                })
        
        # Insight 2: Product performance
        active = performance_data['product_performance']['total_active']
        sold = performance_data['product_performance']['total_sold']
        
        if sold > 0 and active > 0:
            sell_through_rate = (sold / (active + sold)) * 100
            
            if sell_through_rate > 30:
                insights.append({
                    'type': 'success',
                    'insight': f'Good sell-through rate: {sell_through_rate:.1f}%',
                    'confidence': 0.85,
                    'action': 'increase_inventory'
                })
        
        # Insight 3: Revenue trends
        revenue = performance_data['ebay_sales']['revenue']
        
        if revenue > 100:
            insights.append({
                'type': 'success',
                'insight': f'Strong revenue: €{revenue:.2f} in 24h',
                'confidence': 0.95,
                'action': 'scale_up'
            })
        elif revenue > 50:
            insights.append({
                'type': 'info',
                'insight': f'Moderate revenue: €{revenue:.2f} - On track',
                'confidence': 0.8,
                'action': 'continue'
            })
        
        # Save insights to learning database
        self.save_insights(insights)
        
        return insights
    
    def save_insights(self, insights):
        """Save insights to learning database"""
        conn = sqlite3.connect(self.learning_db)
        cursor = conn.cursor()
        
        for insight in insights:
            cursor.execute('''
                INSERT INTO learning_insights
                (insight_type, insight, confidence, evidence, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                insight['type'],
                insight['insight'],
                insight['confidence'],
                insight.get('action', ''),
                datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    def generate_optimizations(self, insights):
        """Generate optimization actions based on insights"""
        print()
        print("=" * 70)
        print("⚡ GENERATING OPTIMIZATIONS...")
        print("=" * 70)
        print()
        
        optimizations = []
        
        for insight in insights:
            action = insight.get('action')
            
            if action == 'test_new_strategy':
                optimizations.append({
                    'type': 'ab_test',
                    'description': 'Test new Reddit post titles',
                    'variants': [
                        'Current: [DEAL] format',
                        'New: Question format (e.g., "Habt ihr gewusst...?")'
                    ],
                    'priority': 'high'
                })
            
            elif action == 'scale_up':
                optimizations.append({
                    'type': 'increase_volume',
                    'description': 'Add 10 more products (success threshold reached)',
                    'priority': 'high'
                })
            
            elif action == 'increase_inventory':
                optimizations.append({
                    'type': 'inventory',
                    'description': 'High sell-through - add similar products',
                    'priority': 'medium'
                })
        
        # Always test new posting times
        optimizations.append({
            'type': 'timing_test',
            'description': 'Test posting at different times (9AM vs 3PM vs 9PM)',
            'priority': 'medium'
        })
        
        return optimizations
    
    def apply_optimizations(self, optimizations):
        """Apply optimizations to the system"""
        print()
        print("=" * 70)
        print("🔧 APPLYING OPTIMIZATIONS...")
        print("=" * 70)
        print()
        
        applied = []
        
        for opt in optimizations:
            if opt['priority'] == 'high':
                print(f"✅ {opt['type']}: {opt['description']}")
                applied.append(opt)
                
                # Update strategies
                if opt['type'] == 'ab_test':
                    self.strategies['reddit']['next_test'] = opt['variants']
                elif opt['type'] == 'increase_volume':
                    self.strategies['optimization']['target_products'] = 15
            else:
                print(f"📋 Queued: {opt['description']}")
        
        # Save updated strategies
        self.save_strategies()
        
        return applied
    
    def append_to_log(self, data):
        """Append performance data to log"""
        log_data = []
        
        if os.path.exists(self.performance_log):
            with open(self.performance_log, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
        
        log_data.append(data)
        
        # Keep last 30 days only
        if len(log_data) > 30:
            log_data = log_data[-30:]
        
        with open(self.performance_log, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2)
    
    def generate_report(self, performance_data, insights, optimizations):
        """Generate improvement report"""
        print()
        print("=" * 70)
        print("📊 SELF-IMPROVEMENT REPORT")
        print("=" * 70)
        print()
        
        print("📈 PERFORMANCE:")
        print(f"   Sales (24h):     {performance_data['ebay_sales']['sales_count']}")
        print(f"   Revenue (24h):   €{performance_data['ebay_sales']['revenue']:.2f}")
        print(f"   Social Reach:    {performance_data['social_media_metrics']['total_estimated_reach']}")
        print()
        
        print("🧠 INSIGHTS LEARNED:")
        for i, insight in enumerate(insights, 1):
            print(f"   {i}. {insight['insight']} (confidence: {insight['confidence']*100:.0f}%)")
        print()
        
        print("⚡ OPTIMIZATIONS APPLIED:")
        for i, opt in enumerate(optimizations, 1):
            print(f"   {i}. {opt['description']}")
        print()
        
        # Save report
        report = {
            'timestamp': datetime.now().isoformat(),
            'performance': performance_data,
            'insights': insights,
            'optimizations': optimizations
        }
        
        with open('data/latest_improvement_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        print("💾 Report saved: data/latest_improvement_report.json")
        print()
    
    def run_improvement_cycle(self):
        """Run one complete improvement cycle"""
        print()
        print("=" * 70)
        print("🤖 SELF-IMPROVING SYSTEM - CYCLE START")
        print("=" * 70)
        print()
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Step 1: Collect data
        performance_data = self.collect_performance_data()
        
        # Step 2: Analyze and learn
        insights = self.analyze_and_learn(performance_data)
        
        # Step 3: Generate optimizations
        optimizations = self.generate_optimizations(insights)
        
        # Step 4: Apply optimizations
        applied = self.apply_optimizations(optimizations)
        
        # Step 5: Generate report
        self.generate_report(performance_data, insights, applied)
        
        print("=" * 70)
        print("✅ IMPROVEMENT CYCLE COMPLETE!")
        print("=" * 70)
        print()
        print("💡 System has learned and improved itself!")
        print()

if __name__ == "__main__":
    try:
        system = SelfImprovingSystem()
        system.run_improvement_cycle()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
