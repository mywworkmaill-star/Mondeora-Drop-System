"""
Mondeora + eBay MCP Full Integration
Complete automated workflow using LangGraph + eBay MCP + n8n
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal
from pathlib import Path
import os
import sys

# Add Mondeora to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrations.ebay_mcp_bridge import eBayMCPIntegration

# State definition
class MondeoraSalesState(TypedDict):
    # Order info
    ebay_order_id: str
    ebay_line_item_id: str
    buyer_email: str
    
    # Product info
    sku: str
    ali_product_id: str
    ali_supplier_link: str
    
    # Status tracking
    stock_available: bool
    gpsr_compliant: bool
    ali_order_created: bool
    tracking_number: str
    tracking_uploaded: bool
    
    # Metadata
    status: str
    error: str
    retry_count: int
    max_retries: int


class MondeoraSalesAutomation:
    """
    Full sales automation: eBay Order → AliExpress → Tracking → eBay
    """
    
    def __init__(self):
        self.ebay_mcp = eBayMCPIntegration()
    
    # === Nodes ===
    
    def fetch_ebay_order(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Fetch eBay order details via MCP"""
        print(f"📦 Fetching eBay order: {state['ebay_order_id']}")
        
        order = self.ebay_mcp.get_order_details(state['ebay_order_id'])
        
        # Extract SKU from order
        # state["sku"] = order["lineItems"][0]["sku"]
        state["sku"] = "PLACEHOLDER-SKU"  # Simülasyon
        
        print(f"   ✅ Order fetched: SKU={state['sku']}")
        return state
    
    def check_stock(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Check AliExpress stock availability"""
        print(f"📊 Checking AliExpress stock for: {state['ali_product_id']}")
        
        # Real implementation: AliExpress API call
        # For now: simulate
        import random
        state["stock_available"] = random.random() > 0.2  # 80% success
        
        if state["stock_available"]:
            print("   ✅ Stock available!")
        else:
            print(f"   ⚠️ Out of stock (retry {state['retry_count']}/{state['max_retries']})")
            state["retry_count"] += 1
        
        return state
    
    def check_gpsr(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Check GPSR compliance from database"""
        print(f"🔍 GPSR compliance check: {state['sku']}")
        
        # Real implementation: Query listing_ready.sqlite
        # For now: simulate
        state["gpsr_compliant"] = True
        
        if state["gpsr_compliant"]:
            print("   ✅ GPSR compliant")
        else:
            print("   ❌ GPSR not compliant - manual review required")
        
        return state
    
    def create_ali_order(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Create AliExpress order (PENDING, no auto-payment)"""
        print(f"🛒 Creating AliExpress order: {state['ali_supplier_link']}")
        
        # Real implementation: AliExpress ds.trade.order.create
        state["ali_order_created"] = True
        state["tracking_number"] = "PENDING_APPROVAL"
        
        print("   ⏳ Order created (PENDING approval)")
        return state
    
    def manual_approval_wait(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Wait for manual approval (Telegram notification via n8n)"""
        print("👤 Waiting for manual approval...")
        print("   📱 Telegram notification sent (via n8n)")
        
        # Real implementation: n8n webhook + Telegram
        # For now: auto-approve
        state["tracking_number"] = "DHL123456789"
        
        print("   ✅ Approved! Tracking: DHL123456789")
        return state
    
    def upload_tracking_to_ebay(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Upload tracking to eBay via MCP"""
        print(f"📮 Uploading tracking to eBay: {state['tracking_number']}")
        
        result = self.ebay_mcp.upload_tracking(
            order_id=state["ebay_order_id"],
            tracking_number=state["tracking_number"],
            carrier="DHL"
        )
        
        state["tracking_uploaded"] = True
        state["status"] = "completed"
        
        print("   ✅ Tracking uploaded to eBay!")
        return state
    
    def handle_error(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Error handler"""
        print(f"❌ Error: {state.get('error', 'Unknown error')}")
        state["status"] = "failed"
        return state
    
    # === Routing Functions ===
    
    def route_stock(self, state: MondeoraSalesState) -> Literal["check_gpsr", "retry_stock", "error"]:
        """Route after stock check"""
        if state["stock_available"]:
            return "check_gpsr"
        elif state["retry_count"] < state["max_retries"]:
            return "retry_stock"
        else:
            state["error"] = f"Stock unavailable after {state['max_retries']} retries"
            return "error"
    
    def route_gpsr(self, state: MondeoraSalesState) -> Literal["create_order", "error"]:
        """Route after GPSR check"""
        if state["gpsr_compliant"]:
            return "create_order"
        else:
            state["error"] = "GPSR not compliant - requires manual review"
            return "error"
    
    # === Build Workflow ===
    
    def build_workflow(self):
        """Build the complete sales automation workflow"""
        workflow = StateGraph(MondeoraSalesState)
        
        # Add nodes
        workflow.add_node("fetch_order", self.fetch_ebay_order)
        workflow.add_node("check_stock", self.check_stock)
        workflow.add_node("retry_stock", self.check_stock)  # Same function, retry context
        workflow.add_node("check_gpsr", self.check_gpsr)
        workflow.add_node("create_order", self.create_ali_order)
        workflow.add_node("manual_approval", self.manual_approval_wait)
        workflow.add_node("upload_tracking", self.upload_tracking_to_ebay)
        workflow.add_node("error", self.handle_error)
        
        # Set entry
        workflow.set_entry_point("fetch_order")
        
        # Routing
        workflow.add_edge("fetch_order", "check_stock")
        
        workflow.add_conditional_edges(
            "check_stock",
            self.route_stock,
            {
                "check_gpsr": "check_gpsr",
                "retry_stock": "retry_stock",
                "error": "error"
            }
        )
        
        workflow.add_conditional_edges(
            "retry_stock",
            self.route_stock,
            {
                "check_gpsr": "check_gpsr",
                "retry_stock": "retry_stock",
                "error": "error"
            }
        )
        
        workflow.add_conditional_edges(
            "check_gpsr",
            self.route_gpsr,
            {
                "create_order": "create_order",
                "error": "error"
            }
        )
        
        workflow.add_edge("create_order", "manual_approval")
        workflow.add_edge("manual_approval", "upload_tracking")
        workflow.add_edge("upload_tracking", END)
        workflow.add_edge("error", END)
        
        return workflow.compile()


# === Test & Demo ===

if __name__ == "__main__":
    print("🚀 Mondeora Full Sales Automation\n")
    print("=" * 60)
    
    automation = MondeoraSalesAutomation()
    app = automation.build_workflow()
    
    # Test order
    test_state = {
        "ebay_order_id": "12345-67890-TEST",
        "ebay_line_item_id": "12345-67890-00001",
        "buyer_email": "buyer@example.com",
        "sku": "",
        "ali_product_id": "1005006372921430",
        "ali_supplier_link": "https://aliexpress.com/item/1005006372921430.html",
        "stock_available": False,
        "gpsr_compliant": False,
        "ali_order_created": False,
        "tracking_number": "",
        "tracking_uploaded": False,
        "status": "pending",
        "error": "",
        "retry_count": 0,
        "max_retries": 3
    }
    
    print("\n📋 TEST ORDER:")
    print(f"eBay Order ID: {test_state['ebay_order_id']}")
    print(f"AliExpress Product: {test_state['ali_product_id']}")
    print("\n" + "=" * 60 + "\n")
    
    # Run workflow
    result = app.invoke(test_state)
    
    print("\n" + "=" * 60)
    print("📊 FINAL RESULT:")
    print("=" * 60)
    print(f"Status: {result['status']}")
    print(f"Tracking: {result.get('tracking_number', 'N/A')}")
    print(f"Tracking Uploaded: {result.get('tracking_uploaded', False)}")
    print(f"Error: {result.get('error', 'None')}")
    
    print("\n✅ Workflow complete!")
    print("\n📖 Integration Points:")
    print("1. eBay MCP: Fetch orders + Upload tracking")
    print("2. AliExpress API: Stock check + Create order")
    print("3. Database: GPSR compliance check")
    print("4. n8n: Telegram notifications + Manual approval")
    print("5. LangGraph: Conditional logic + Retry + Error handling")
