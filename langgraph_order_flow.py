"""
LangGraph Order Fulfillment Workflow
Mondeora için sipariş işleme akışı
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal
import os

# State tanımı
class OrderState(TypedDict):
    order_id: str
    product_id: str
    stock_available: bool
    gpsr_compliant: bool
    payment_approved: bool
    tracking_number: str
    status: str
    error: str

# Node fonksiyonları
def check_stock(state: OrderState) -> OrderState:
    """Stok kontrolü"""
    print(f"📦 Stok kontrolü: {state['product_id']}")
    # Gerçek implementasyon: AliExpress API
    state["stock_available"] = True  # Simülasyon
    return state

def check_gpsr(state: OrderState) -> OrderState:
    """GPSR uygunluk kontrolü"""
    print(f"✅ GPSR kontrolü: {state['product_id']}")
    # Gerçek implementasyon: database check
    state["gpsr_compliant"] = True  # Simülasyon
    return state

def create_aliexpress_order(state: OrderState) -> OrderState:
    """AliExpress'te sipariş oluştur"""
    print(f"🛒 AliExpress sipariş oluşturma: {state['order_id']}")
    # Gerçek implementasyon: AliExpress API
    state["tracking_number"] = "FAKE123456789"  # Simülasyon
    return state

def upload_tracking(state: OrderState) -> OrderState:
    """Tracking number'ı eBay'e yükle"""
    print(f"📮 Tracking eBay'e yükleniyor: {state['tracking_number']}")
    # Gerçek implementasyon: eBay API
    state["status"] = "completed"
    return state

def handle_error(state: OrderState) -> OrderState:
    """Hata yönetimi"""
    print(f"❌ Hata: {state.get('error', 'Bilinmeyen hata')}")
    state["status"] = "failed"
    return state

# Conditional routing
def route_stock(state: OrderState) -> Literal["check_gpsr", "error"]:
    """Stok varsa GPSR kontrolüne, yoksa hata"""
    if state["stock_available"]:
        return "check_gpsr"
    else:
        state["error"] = "Stok yok"
        return "error"

def route_gpsr(state: OrderState) -> Literal["create_order", "error"]:
    """GPSR tamam ise sipariş oluştur, değilse hata"""
    if state["gpsr_compliant"]:
        return "create_order"
    else:
        state["error"] = "GPSR uyumsuz"
        return "error"

# Graph oluştur
def build_order_workflow():
    workflow = StateGraph(OrderState)
    
    # Node'ları ekle
    workflow.add_node("check_stock", check_stock)
    workflow.add_node("check_gpsr", check_gpsr)
    workflow.add_node("create_order", create_aliexpress_order)
    workflow.add_node("upload_tracking", upload_tracking)
    workflow.add_node("error", handle_error)
    
    # Başlangıç
    workflow.set_entry_point("check_stock")
    
    # Conditional edges (karar noktaları)
    workflow.add_conditional_edges(
        "check_stock",
        route_stock,
        {
            "check_gpsr": "check_gpsr",
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
    workflow.add_edge("create_order", "upload_tracking")
    workflow.add_edge("upload_tracking", END)
    workflow.add_edge("error", END)
    
    return workflow.compile()

# Test
if __name__ == "__main__":
    print("🚀 LangGraph Order Workflow Test\n")
    
    # Workflow'u derle
    app = build_order_workflow()
    
    # Test case 1: Başarılı sipariş
    print("=" * 50)
    print("TEST 1: Başarılı Sipariş")
    print("=" * 50)
    initial_state = {
        "order_id": "eBay-123456",
        "product_id": "ALI-789012",
        "stock_available": False,  # İlk değer (node güncelleyecek)
        "gpsr_compliant": False,
        "payment_approved": False,
        "tracking_number": "",
        "status": "pending",
        "error": ""
    }
    
    result = app.invoke(initial_state)
    print(f"\n✅ Son durum: {result['status']}")
    print(f"📦 Tracking: {result.get('tracking_number', 'N/A')}")
    
    # Test case 2: Stok yok hatası
    print("\n" + "=" * 50)
    print("TEST 2: Stok Yok Hatası")
    print("=" * 50)
    
    # Stock check'i False döndürecek şekilde override edelim
    def check_stock_fail(state):
        state["stock_available"] = False
        return state
    
    workflow2 = StateGraph(OrderState)
    workflow2.add_node("check_stock", check_stock_fail)
    workflow2.add_node("check_gpsr", check_gpsr)
    workflow2.add_node("create_order", create_aliexpress_order)
    workflow2.add_node("upload_tracking", upload_tracking)
    workflow2.add_node("error", handle_error)
    workflow2.set_entry_point("check_stock")
    workflow2.add_conditional_edges("check_stock", route_stock, {"check_gpsr": "check_gpsr", "error": "error"})
    workflow2.add_conditional_edges("check_gpsr", route_gpsr, {"create_order": "create_order", "error": "error"})
    workflow2.add_edge("create_order", "upload_tracking")
    workflow2.add_edge("upload_tracking", END)
    workflow2.add_edge("error", END)
    
    app2 = workflow2.compile()
    result2 = app2.invoke(initial_state)
    print(f"\n❌ Son durum: {result2['status']}")
    print(f"⚠️ Hata: {result2.get('error', 'N/A')}")
    
    print("\n" + "=" * 50)
    print("✅ LangGraph kuruldu ve çalışıyor!")
    print("=" * 50)
    print("\n📖 Kullanım:")
    print("1. Graph oluştur: build_order_workflow()")
    print("2. State tanımla: OrderState dict")
    print("3. Çalıştır: app.invoke(state)")
    print("\n🔗 Mondeora'ya entegre etmek için:")
    print("   - src/jobs/order_fulfillment.py içinde kullan")
    print("   - Her node'u gerçek API çağrılarına bağla")
    print("   - Retry/timeout mekanizmaları ekle")
