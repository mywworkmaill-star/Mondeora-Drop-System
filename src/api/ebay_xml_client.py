"""
eBay XML API - Automated Inventory Management
AddItem, ReviseItem, GetItem operations
"""

import os
import requests
from xml.etree import ElementTree as ET
from defusedxml.ElementTree import fromstring as _safe_fromstring
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class EbayXMLAPIClient:
    def __init__(self):
        self.auth_token = os.getenv("EBAY_ACCESS_TOKEN")
        self.dev_id = os.getenv("EBAY_DEV_ID")
        self.app_id = os.getenv("EBAY_APP_ID")
        self.cert_id = os.getenv("EBAY_CERT_ID")
        self.siteid = "77"  # Germany
        
        self.endpoint = "https://api.ebay.com/ws/api.dll"
        self.ns = {'ebay': 'urn:ebay:apis:eBLBaseComponents'}
    
    def _get_headers(self, call_name):
        """XML API headers"""
        return {
            'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
            'X-EBAY-API-DEV-NAME': self.dev_id,
            'X-EBAY-API-APP-NAME': self.app_id,
            'X-EBAY-API-CERT-NAME': self.cert_id,
            'X-EBAY-API-SITEID': self.siteid,
            'X-EBAY-API-CALL-NAME': call_name,
            'Content-Type': 'application/xml',
        }
    
    def add_item(self, product):
        """
        AddItem - Ürün eBay'a ekle
        
        product = {
            'sku': 'PROD-001',
            'title': 'Product Title',
            'description': 'Product description',
            'price': 25.99,
            'quantity': 10,
            'category': 15687,
        }
        """
        
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<AddItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    <RequesterCredentials>
        <eBayAuthToken>{self.auth_token}</eBayAuthToken>
    </RequesterCredentials>
    <Item>
        <Title>{product['title']}</Title>
        <Description>{product.get('description', '')}</Description>
        <PrimaryCategory>
            <CategoryID>{product.get('category', 15687)}</CategoryID>
        </PrimaryCategory>
        <StartPrice>{product['price']}</StartPrice>
        <Currency>EUR</Currency>
        <Quantity>{product.get('quantity', 1)}</Quantity>
        <ListingType>FixedPriceItem</ListingType>
        <Condition>
            <ConditionID>3000</ConditionID>
        </Condition>
        <Location>Germany</Location>
        <Country>DE</Country>
        <Site>Germany</Site>
        <SKU>{product['sku']}</SKU>
    </Item>
    <ErrorLanguage>en_US</ErrorLanguage>
</AddItemRequest>"""
        
        return self._send_request('AddItem', xml)
    
    def revise_item(self, item_id, quantity, price=None):
        """
        ReviseItem - Inventory update (quantity, price)
        """
        
        price_xml = f"<StartPrice>{price}</StartPrice>" if price else ""
        
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ReviseItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    <RequesterCredentials>
        <eBayAuthToken>{self.auth_token}</eBayAuthToken>
    </RequesterCredentials>
    <Item>
        <ItemID>{item_id}</ItemID>
        <Quantity>{quantity}</Quantity>
        {price_xml}
    </Item>
    <ErrorLanguage>en_US</ErrorLanguage>
</ReviseItemRequest>"""
        
        return self._send_request('ReviseItem', xml)
    
    def get_item(self, item_id):
        """
        GetItem - Ürün bilgilerini getir
        """
        
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<GetItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    <RequesterCredentials>
        <eBayAuthToken>{self.auth_token}</eBayAuthToken>
    </RequesterCredentials>
    <ItemID>{item_id}</ItemID>
    <ErrorLanguage>en_US</ErrorLanguage>
</GetItemRequest>"""
        
        return self._send_request('GetItem', xml)
    
    def _send_request(self, call_name, xml_body):
        """XML request gönder ve response parse et"""
        
        headers = self._get_headers(call_name)
        
        try:
            response = requests.post(
                self.endpoint,
                data=xml_body,
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                root = _safe_fromstring(response.content)
                ack = root.find('.//ebay:Ack', self.ns)
                
                if ack is not None and ack.text == "Success":
                    return {
                        "success": True,
                        "ack": ack.text,
                        "root": root,
                    }
                else:
                    errors = root.findall('.//ebay:Error', self.ns)
                    error_msgs = []
                    for error in errors:
                        msg = error.find('.//ebay:ShortMessage', self.ns)
                        if msg is not None:
                            error_msgs.append(msg.text)
                    
                    return {
                        "success": False,
                        "ack": ack.text if ack is not None else "Unknown",
                        "errors": error_msgs,
                    }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "response": response.text[:300],
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

if __name__ == "__main__":
    client = EbayXMLAPIClient()
    
    # Test AddItem
    test_product = {
        'sku': f"TEST-{int(datetime.now().timestamp())}",
        'title': 'Test Product',
        'description': 'Test product from automation',
        'price': 25.99,
        'quantity': 10,
        'category': 15687,
    }
    
    result = client.add_item(test_product)
    print(f"AddItem Result: {result}")
