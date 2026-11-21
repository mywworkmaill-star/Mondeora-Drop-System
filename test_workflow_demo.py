"""
Mondeora Full Automation - DEMO TEST
Test workflow without requiring eBay credentials
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal
import time

# State definition
class MondeoraSalesState(TypedDict):
    # Order info
    ebay_order_id: str
    sku: str
    ali_product_id: str
    
    # Status tracking
    stock_available: bool
    gpsr_compliant: bool
    tracking_number: str
    
    # Metadata
    status: str
    error: str
    retry_count: int
    max_retries: int


class MondeoraDemoAutomation:
    """
    Demo workflow - shows all steps without real API calls
    """
    
    def __init__(self):
        self.max_retries = 3
    
    def fetch_ebay_order(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Simulate: Fetch eBay order via eBay MCP"""
        print(f"\n📦 [STEP 1] Fetching eBay order: {state['ebay_order_id']}")
        time.sleep(1)
        print(f"   ✅ Order fetched: SKU={state['sku']}")
        state['status'] = 'order_fetched'
        return state
    
    def check_stock(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Simulate: Check AliExpress stock"""
        print(f"\n📊 [STEP 2] Checking AliExpress stock: {state['ali_product_id']}")
        time.sleep(1)
        
        # Simulate stock available
        state['stock_available'] = True
        print(f"   ✅ Stock available!")
        state['status'] = 'stock_checked'
        return state
    
    def check_gpsr(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Simulate: GPSR compliance check"""
        print(f"\n🔍 [STEP 3] GPSR compliance check: {state['sku']}")
        time.sleep(1)
        
        # Simulate GPSR compliant
        state['gpsr_compliant'] = True
        print(f"   ✅ GPSR compliant")
        state['status'] = 'gpsr_checked'
        return state
    
    def create_ali_order(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Simulate: Create AliExpress PENDING order"""
        print(f"\n🛒 [STEP 4] Creating AliExpress order...")
        time.sleep(1)
        print(f"   ⏳ Order created (PENDING approval)")
        state['status'] = 'ali_order_pending'
        return state
    
    def manual_approval(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Simulate: Manual approval via Telegram"""
        print(f"\n👤 [STEP 5] Waiting for manual approval...")
        print(f"   📱 Telegram notification sent (via n8n)")
        time.sleep(2)
        
        # Simulate approval and tracking received
        state['tracking_number'] = 'DHL123456789'
        print(f"   ✅ Approved! Tracking: {state['tracking_number']}")
        state['status'] = 'approved'
        return state
    
    def upload_tracking(self, state: MondeoraSalesState) -> MondeoraSalesState:
        """Simulate: Upload tracking to eBay via eBay MCP"""
        print(f"\n📮 [STEP 6] Uploading tracking to eBay: {state['tracking_number']}")
        time.sleep(1)
        print(f"   ✅ Tracking uploaded to eBay!")
        state['status'] = 'completed'
        return state
    
    # Conditional routing
    def should_retry_stock(self, state: MondeoraSalesState) -> Literal["retry", "proceed", "fail"]:
        """Route: Check if stock retry needed"""
        if state['stock_available']:
            return "proceed"
        elif state['retry_count'] < state['max_retries']:
            return "retry"
        else:
            return "fail"
    
    def should_proceed_gpsr(self, state: MondeoraSalesState) -> Literal["proceed", "manual_review"]:
        """Route: Check GPSR compliance"""
        return "proceed" if state['gpsr_compliant'] else "manual_review"
    
    def build_workflow(self):
        """Build LangGraph workflow"""
        workflow = StateGraph(MondeoraSalesState)
        
        # Add nodes
        workflow.add_node("fetch_ebay_order", self.fetch_ebay_order)
        workflow.add_node("check_stock", self.check_stock)
        workflow.add_node("check_gpsr", self.check_gpsr)
        workflow.add_node("create_ali_order", self.create_ali_order)
        workflow.add_node("manual_approval", self.manual_approval)
        workflow.add_node("upload_tracking", self.upload_tracking)
        
        # Set entry point
        workflow.set_entry_point("fetch_ebay_order")
        
        # Add edges
        workflow.add_edge("fetch_ebay_order", "check_stock")
        
        # Conditional: stock check with retry
        workflow.add_conditional_edges(
            "check_stock",
            self.should_retry_stock,
            {
                "proceed": "check_gpsr",
                "retry": "check_stock",
                "fail": END
            }
        )
        
        # Conditional: GPSR check
        workflow.add_conditional_edges(
            "check_gpsr",
            self.should_proceed_gpsr,
            {
                "proceed": "create_ali_order",
                "manual_review": END
            }
        )
        
        workflow.add_edge("create_ali_order", "manual_approval")
        workflow.add_edge("manual_approval", "upload_tracking")
        workflow.add_edge("upload_tracking", END)
        
        return workflow.compile()


def main():
    """Run demo workflow"""
    print("=" * 60)
    print("🚀 Mondeora Full Sales Automation - DEMO")
    print("=" * 60)
    
    # Initialize automation
    automation = MondeoraDemoAutomation()
    app = automation.build_workflow()
    
    # Test order
    test_order = {
        "ebay_order_id": "12345-67890-DEMO",
        "sku": "DEMO-PRODUCT-001",
        "ali_product_id": "1005006372921430",
        "stock_available": False,
        "gpsr_compliant": False,
        "tracking_number": "",
        "status": "initialized",
        "error": "",
        "retry_count": 0,
        "max_retries": 3
    }
    
    print(f"\n📋 TEST ORDER:")
    print(f"   eBay Order ID: {test_order['ebay_order_id']}")
    print(f"   SKU: {test_order['sku']}")
    print(f"   AliExpress Product: {test_order['ali_product_id']}")
    print("=" * 60)
    
    # Run workflow
    result = app.invoke(test_order)
    
    # Print results
    print("\n" + "=" * 60)
    print("📊 FINAL RESULT:")
    print("=" * 60)
    print(f"Status: {result['status']}")
    print(f"Stock Available: {result['stock_available']}")
    print(f"GPSR Compliant: {result['gpsr_compliant']}")
    print(f"Tracking: {result['tracking_number']}")
    print(f"Error: {result['error'] or 'None'}")
    print("\n✅ Workflow complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
