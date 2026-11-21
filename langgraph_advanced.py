"""
LangGraph Advanced: Retry + Visualization
Mondeora için gelişmiş workflow özellikleri
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal, Annotated
from langgraph.checkpoint.memory import MemorySaver
import json

# State tanımı (retry counter eklenmiş)
class AdvancedOrderState(TypedDict):
    order_id: str
    product_id: str
    stock_available: bool
    gpsr_compliant: bool
    tracking_number: str
    status: str
    error: str
    retry_count: int
    max_retries: int

# Retry ile node
def check_stock_with_retry(state: AdvancedOrderState) -> AdvancedOrderState:
    """Stok kontrolü (retry desteği)"""
    print(f"📦 Stok kontrolü (deneme {state['retry_count'] + 1}/{state['max_retries']}): {state['product_id']}")
    
    # Simülasyon: %70 başarı oranı
    import random
    success = random.random() > 0.3
    
    if success:
        state["stock_available"] = True
        state["retry_count"] = 0  # Reset
        print("   ✅ Stok var!")
    else:
        state["stock_available"] = False
        state["retry_count"] += 1
        print(f"   ⚠️ API hatası, retry {state['retry_count']}/{state['max_retries']}")
    
    return state

def check_gpsr_with_validation(state: AdvancedOrderState) -> AdvancedOrderState:
    """GPSR kontrolü (database + AI validation)"""
    print(f"🔍 GPSR kontrolü: {state['product_id']}")
    
    # Gerçek implementasyon:
    # 1. Database'de GPSR evidence var mı?
    # 2. AI ile ürün açıklaması GPSR'a uygun mu?
    
    state["gpsr_compliant"] = True  # Simülasyon
    print("   ✅ GPSR uyumlu")
    return state

def create_aliexpress_order_safe(state: AdvancedOrderState) -> AdvancedOrderState:
    """AliExpress sipariş (pending, otomatik ödeme YOK)"""
    print(f"🛒 AliExpress PENDING sipariş: {state['order_id']}")
    
    # Gerçek implementasyon: ds.trade.order.create (payment=pending)
    state["tracking_number"] = "PENDING_APPROVAL"
    print("   ⏳ Manuel onay bekleniyor...")
    return state

def manual_approval_wait(state: AdvancedOrderState) -> AdvancedOrderState:
    """Manuel onay simülasyonu"""
    print("👤 Manuel onay bekleniyor (gerçekte: Telegram notification)")
    
    # Gerçek implementasyon:
    # 1. Telegram'a bildirim gönder
    # 2. n8n webhook'u bekle
    # 3. Kullanıcı onayı gelince devam et
    
    state["tracking_number"] = "REAL123456789"
    print("   ✅ Onaylandı!")
    return state

# Conditional routing (retry mantığı)
def route_stock_with_retry(state: AdvancedOrderState) -> Literal["check_gpsr", "retry_stock", "error"]:
    """Stok kontrolü sonrası routing"""
    if state["stock_available"]:
        return "check_gpsr"
    elif state["retry_count"] < state["max_retries"]:
        return "retry_stock"  # Tekrar dene
    else:
        state["error"] = f"Stok kontrolü başarısız ({state['max_retries']} deneme)"
        return "error"

def route_gpsr(state: AdvancedOrderState) -> Literal["create_order", "error"]:
    if state["gpsr_compliant"]:
        return "create_order"
    else:
        state["error"] = "GPSR uyumsuz - supervised trial gerekli"
        return "error"

# Advanced workflow
def build_advanced_workflow():
    # Memory saver (state'i kaydet)
    memory = MemorySaver()
    
    workflow = StateGraph(AdvancedOrderState)
    
    # Nodes
    workflow.add_node("check_stock", check_stock_with_retry)
    workflow.add_node("retry_stock", check_stock_with_retry)  # Aynı fonksiyon, retry için
    workflow.add_node("check_gpsr", check_gpsr_with_validation)
    workflow.add_node("create_order", create_aliexpress_order_safe)
    workflow.add_node("manual_approval", manual_approval_wait)
    workflow.add_node("error", lambda s: {**s, "status": "failed"})
    workflow.add_node("success", lambda s: {**s, "status": "completed"})
    
    # Entry point
    workflow.set_entry_point("check_stock")
    
    # Routing
    workflow.add_conditional_edges(
        "check_stock",
        route_stock_with_retry,
        {
            "check_gpsr": "check_gpsr",
            "retry_stock": "retry_stock",
            "error": "error"
        }
    )
    
    workflow.add_conditional_edges(
        "retry_stock",
        route_stock_with_retry,
        {
            "check_gpsr": "check_gpsr",
            "retry_stock": "retry_stock",
            "error": "error"
        }
    )
    
    workflow.add_conditional_edges(
        "check_gpsr",
        route_gpsr,
        {
            "create_order": "create_order",
            "error": "error"
        }
    )
    
    # Normal edges
    workflow.add_edge("create_order", "manual_approval")
    workflow.add_edge("manual_approval", "success")
    workflow.add_edge("error", END)
    workflow.add_edge("success", END)
    
    return workflow.compile(checkpointer=memory)

# Workflow görselleştirme (ASCII)
def visualize_workflow():
    """Workflow'u ASCII art olarak göster"""
    diagram = """
    ┌─────────────────────────────────────────────────────┐
    │          MONDEORA ORDER FULFILLMENT FLOW            │
    └─────────────────────────────────────────────────────┘
    
         [eBay Order Received]
                  │
                  ▼
         ┌─────────────────┐
         │  Check Stock    │◄─────┐
         │  (AliExpress)   │      │ Retry
         └────────┬────────┘      │ (max 3x)
                  │                │
         ┌────────┴────────┐      │
         │   Stock OK?     ├──No──┘
         └────────┬────────┘
                  │ Yes
                  ▼
         ┌─────────────────┐
         │  Check GPSR     │
         │  (Database)     │
         └────────┬────────┘
                  │
         ┌────────┴────────┐
         │  GPSR OK?       ├──No──► [ERROR: Manual Review]
         └────────┬────────┘
                  │ Yes
                  ▼
         ┌─────────────────┐
         │ Create Order    │
         │  (PENDING)      │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ Manual Approval │◄──── [Telegram Notification]
         │  (Telegram)     │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ Upload Tracking │
         │   to eBay       │
         └────────┬────────┘
                  │
                  ▼
            [COMPLETED]
    """
    return diagram

# Test
if __name__ == "__main__":
    print(visualize_workflow())
    print("\n" + "=" * 60)
    print("🧪 ADVANCED WORKFLOW TEST (Retry + Manual Approval)")
    print("=" * 60 + "\n")
    
    app = build_advanced_workflow()
    
    initial_state = {
        "order_id": "eBay-456789",
        "product_id": "ALI-999888",
        "stock_available": False,
        "gpsr_compliant": False,
        "tracking_number": "",
        "status": "pending",
        "error": "",
        "retry_count": 0,
        "max_retries": 3
    }
    
    # Thread ID ile state tracking
    thread_id = "order_456789"
    config = {"configurable": {"thread_id": thread_id}}
    
    result = app.invoke(initial_state, config)
    
    print("\n" + "=" * 60)
    print(f"📊 SONUÇ:")
    print("=" * 60)
    print(f"Status      : {result['status']}")
    print(f"Tracking    : {result.get('tracking_number', 'N/A')}")
    print(f"Retry Count : {result['retry_count']}/{result['max_retries']}")
    print(f"Error       : {result.get('error', 'None')}")
    
    print("\n" + "=" * 60)
    print("✅ LANGGRAPH HAZIR!")
    print("=" * 60)
    print("\n📋 Mondeora Entegrasyon Adımları:")
    print("1. src/jobs/order_fulfillment_langgraph.py oluştur")
    print("2. Her node'u gerçek API fonksiyonlarına bağla:")
    print("   - check_stock → AliExpress ds.text.search API")
    print("   - check_gpsr → data/listing_ready.sqlite query")
    print("   - create_order → ds.trade.order.create (pending=True)")
    print("   - manual_approval → n8n webhook + Telegram notification")
    print("3. Cron job ekle: orders_poll_langgraph")
    print("4. Test et: Supervised trial modunda")
    
    # Graph JSON export (n8n entegrasyonu için)
    print("\n📤 Graph JSON (n8n için):")
    graph_json = {
        "nodes": [
            {"id": "check_stock", "type": "api_call", "api": "aliexpress"},
            {"id": "check_gpsr", "type": "database", "table": "listing_ready"},
            {"id": "create_order", "type": "api_call", "api": "aliexpress"},
            {"id": "manual_approval", "type": "webhook", "platform": "telegram"},
        ],
        "edges": [
            {"from": "check_stock", "to": "check_gpsr", "condition": "stock_ok"},
            {"from": "check_gpsr", "to": "create_order", "condition": "gpsr_ok"},
            {"from": "create_order", "to": "manual_approval"},
        ]
    }
    print(json.dumps(graph_json, indent=2))
