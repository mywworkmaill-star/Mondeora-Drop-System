#!/usr/bin/env python
"""
SELF-EXPANDING AI SYSTEM
Sistem kendine ihtiyacı olan özellikleri otomatik ekler!
"""

import sys
import os
sys.path.insert(0, '.')

import json
from datetime import datetime
import sqlite3

class SelfExpandingAI:
    """
    AI sistem that automatically adds new features to itself based on performance needs
    """
    
    def __init__(self):
        self.db_path = 'data/dropshipping.db'
        self.feature_pool_path = 'feature_pool.json'
        self.expansion_log = 'data/expansion_history.json'
        
        self.load_feature_pool()
        self.load_expansion_history()
    
    def load_feature_pool(self):
        """Load available features from pool"""
        with open(self.feature_pool_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.feature_pool = data['feature_pool']
            self.activation_history = data.get('activation_history', [])
    
    def load_expansion_history(self):
        """Load history of feature activations"""
        if os.path.exists(self.expansion_log):
            with open(self.expansion_log, 'r', encoding='utf-8') as f:
                self.history = json.load(f)
        else:
            self.history = {
                'total_expansions': 0,
                'active_features': [],
                'expansion_timeline': []
            }
    
    def analyze_system_needs(self):
        """Analyze current system performance and identify needs"""
        print()
        print("=" * 70)
        print("🔍 ANALYZING SYSTEM NEEDS...")
        print("=" * 70)
        print()
        
        needs = []
        
        # Get current metrics
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check sales/conversion
        cursor.execute("SELECT COUNT(*) FROM sales WHERE created_at > datetime('now', '-7 days')")
        weekly_sales = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products WHERE status='ACTIVE'")
        active_products = cursor.fetchone()[0]
        
        conversion_rate = (weekly_sales / (active_products * 7)) * 100 if active_products > 0 else 0
        
        print(f"📊 Current Metrics:")
        print(f"   • Weekly Sales: {weekly_sales}")
        print(f"   • Active Products: {active_products}")
        print(f"   • Conversion Rate: {conversion_rate:.2f}%")
        print()
        
        # Analyze needs based on metrics
        if conversion_rate < 2:
            needs.append({
                'type': 'conversion_rate',
                'value': conversion_rate,
                'severity': 'high',
                'reason': f'Low conversion rate: {conversion_rate:.2f}% (target: 2%+)'
            })
        
        if weekly_sales == 0:
            needs.append({
                'type': 'sales_decline',
                'value': 0,
                'severity': 'critical',
                'reason': 'No sales in last 7 days - need traffic/marketing'
            })
        
        if active_products < 10:
            needs.append({
                'type': 'traffic',
                'value': active_products,
                'severity': 'medium',
                'reason': f'Low product count: {active_products} (need more visibility)'
            })
        
        cursor.execute("SELECT COUNT(*) FROM products")
        total_products = cursor.fetchone()[0]
        
        if total_products > 500:
            needs.append({
                'type': 'domestic_saturation',
                'value': total_products,
                'severity': 'low',
                'reason': f'{total_products} products - market saturation approaching'
            })
        
        conn.close()
        
        print(f"⚠️  Identified {len(needs)} needs:")
        for i, need in enumerate(needs, 1):
            print(f"   {i}. [{need['severity'].upper()}] {need['reason']}")
        print()
        
        return needs
    
    def find_matching_features(self, needs):
        """Find features that match current needs"""
        print("=" * 70)
        print("🎯 FINDING MATCHING FEATURES...")
        print("=" * 70)
        print()
        
        matches = []
        
        for feature_key, feature in self.feature_pool.items():
            # Skip already activated features
            if feature_key in self.history['active_features']:
                continue
            
            # Check if feature matches any need
            trigger = feature['activation_trigger']
            for need in needs:
                if trigger['type'] == need['type']:
                    # Calculate match score
                    match_score = self._calculate_match_score(feature, need)
                    
                    matches.append({
                        'feature_key': feature_key,
                        'feature': feature,
                        'need': need,
                        'match_score': match_score
                    })
                    
                    print(f"✅ MATCH: {feature['name']}")
                    print(f"   Need: {need['reason']}")
                    print(f"   Impact: {feature['impact'].upper()}")
                    print(f"   Improvement: {feature['estimated_improvement']}")
                    print(f"   Match Score: {match_score:.1f}/100")
                    print()
        
        # Sort by match score
        matches.sort(key=lambda x: x['match_score'], reverse=True)
        
        return matches
    
    def _calculate_match_score(self, feature, need):
        """Calculate how well a feature matches a need"""
        score = 50  # Base score
        
        # Severity bonus
        severity_bonus = {
            'critical': 30,
            'high': 20,
            'medium': 10,
            'low': 5
        }
        score += severity_bonus.get(need['severity'], 0)
        
        # Impact bonus
        impact_bonus = {
            'very_high': 20,
            'high': 15,
            'medium': 10,
            'low': 5
        }
        score += impact_bonus.get(feature['impact'], 0)
        
        return min(score, 100)
    
    def select_next_feature(self, matches):
        """Select the best feature to activate"""
        if not matches:
            print("❌ No matching features found!")
            return None
        
        print("=" * 70)
        print("🎯 SELECTING NEXT FEATURE TO ACTIVATE...")
        print("=" * 70)
        print()
        
        best_match = matches[0]
        
        print(f"🚀 SELECTED: {best_match['feature']['name']}")
        print(f"   Category: {best_match['feature']['category']}")
        print(f"   Impact: {best_match['feature']['impact'].upper()}")
        print(f"   Difficulty: {best_match['feature']['difficulty']}")
        print(f"   Match Score: {best_match['match_score']:.1f}/100")
        print()
        print(f"📋 Description:")
        print(f"   {best_match['feature']['description']}")
        print()
        print(f"📈 Expected Improvement:")
        print(f"   {best_match['feature']['estimated_improvement']}")
        print()
        
        return best_match
    
    def queue_feature_activation(self, selected_feature):
        """Queue feature for activation"""
        print("=" * 70)
        print("📋 QUEUEING FEATURE FOR ACTIVATION...")
        print("=" * 70)
        print()
        
        activation_request = {
            'feature_key': selected_feature['feature_key'],
            'feature_name': selected_feature['feature']['name'],
            'category': selected_feature['feature']['category'],
            'requested_at': datetime.now().isoformat(),
            'reason': selected_feature['need']['reason'],
            'priority': selected_feature['match_score'],
            'status': 'pending_development',
            'estimated_improvement': selected_feature['feature']['estimated_improvement']
        }
        
        # Update feature pool
        with open(self.feature_pool_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'pending_activations' not in data:
            data['pending_activations'] = []
        
        data['pending_activations'].append(activation_request)
        data['next_feature_priority'] = activation_request
        
        with open(self.feature_pool_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Feature queued: {activation_request['feature_name']}")
        print(f"   Priority: {activation_request['priority']:.1f}/100")
        print(f"   Status: {activation_request['status']}")
        print()
        print("📢 NEXT STEPS:")
        print("   1. Feature will be developed (1-2 days)")
        print("   2. Tested and validated")
        print("   3. Automatically activated")
        print("   4. Performance monitored")
        print()
        
        return activation_request
    
    def run_expansion_cycle(self):
        """Run one complete expansion cycle"""
        print()
        print("=" * 70)
        print("🤖 SELF-EXPANDING AI - LOOKING FOR NEW FEATURES TO ADD")
        print("=" * 70)
        print()
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Step 1: Analyze needs
        needs = self.analyze_system_needs()
        
        if not needs:
            print("✅ System performing well - no new features needed!")
            return None
        
        # Step 2: Find matching features
        matches = self.find_matching_features(needs)
        
        if not matches:
            print("❌ No features available to address current needs")
            return None
        
        # Step 3: Select best feature
        selected = self.select_next_feature(matches)
        
        if not selected:
            return None
        
        # Step 4: Queue for activation
        activation_request = self.queue_feature_activation(selected)
        
        print("=" * 70)
        print("✅ EXPANSION CYCLE COMPLETE!")
        print("=" * 70)
        print()
        print("💡 System has identified next feature to add!")
        print(f"   → {activation_request['feature_name']}")
        print(f"   → Expected: {activation_request['estimated_improvement']}")
        print()
        
        return activation_request

if __name__ == "__main__":
    try:
        ai = SelfExpandingAI()
        ai.run_expansion_cycle()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
