#!/usr/bin/env python3
"""
eBay Access Token Güncelleme Script
.env dosyasını otomatik olarak güncellemek için
"""

import os
import sys
from pathlib import Path

def update_ebay_token(new_token):
    """
    .env dosyasında EBAY_ACCESS_TOKEN'ı güncelle
    
    Args:
        new_token (str): Yeni eBay access token (<EBAY_TOKEN_PLACEHOLDER> formatında)
    """
    env_path = Path(r"C:\Users\Administrator\Desktop\Mondeora-Drop-System\.env")
    
    if not env_path.exists():
        print(f"❌ HATA: .env dosyası bulunamadı: {env_path}")
        return False
    
    print(f"📂 .env dosyası bulundu: {env_path}")
    
    # .env dosyasını oku
    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # EBAY_ACCESS_TOKEN satırını bul ve güncelle
    updated = False
    new_lines = []
    
    for line in lines:
        if line.strip().startswith('EBAY_ACCESS_TOKEN='):
            print(f"📍 Eski token satırı bulundu")
            print(f"   Önce: {line.strip()[:50]}...")
            
            # Yeni token ile değiştir
            new_line = f"EBAY_ACCESS_TOKEN={new_token}\n"
            new_lines.append(new_line)
            
            print(f"   Sonra: {new_line.strip()[:50]}...")
            updated = True
        else:
            new_lines.append(line)
    
    if not updated:
        print("❌ HATA: EBAY_ACCESS_TOKEN satırı .env dosyasında bulunamadı!")
        return False
    
    # Güncellenen .env dosyasını yaz
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"✅ .env dosyası başarıyla güncellendi!")
    print(f"📄 Dosya: {env_path}")
    
    return True

def main():
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║         eBay Access Token Güncelleme Script                   ║")
    print("╚════════════════════════════════════════════════════════════════╝\n")
    
    if len(sys.argv) > 1:
        # Komut satırından token geçildi
        new_token = sys.argv[1]
        print(f"📝 Token komut satırından alındı")
    else:
        # Kullanıcıdan sor
        print("eBay developer portal'dan kopyaladığın yeni token'ı yapıştır:")
        print("(<EBAY_TOKEN_PLACEHOLDER> formatında olmalı)\n")
        
        new_token = input("Token: ").strip()
    
    if not new_token:
        print("❌ HATA: Token boş!")
        return 1
    
    # Token formatını kontrol et
    if not new_token.startswith('v^1.1#'):
        print(f"⚠️  UYARI: Token 'v^1.1#' ile başlamıyor!")
        print(f"   Girilen: {new_token[:30]}...")
        confirm = input("Yine de devam et? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ İptal edildi")
            return 1
    
    print(f"\n📋 Token bilgisi:")
    print(f"   Uzunluk: {len(new_token)} karakter")
    print(f"   Başlangıç: {new_token[:30]}...")
    
    # Güncelleme yap
    success = update_ebay_token(new_token)
    
    if success:
        print("\n✅ BAŞARILI!")
        print("\n📚 Sonraki Adımlar:")
        print("   1. Eğer main.py çalışıyorsa durdur: Ctrl+C")
        print("   2. Yeniden başlat: python main.py")
        print("   3. Logları kontrol et: tail -f logs/system.log")
        print("   4. 'Token refreshed successfully' satırını bekle")
        return 0
    else:
        print("\n❌ BAŞARISIZ!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
