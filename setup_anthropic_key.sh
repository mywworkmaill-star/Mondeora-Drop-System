#!/bin/bash
# ANTHROPIC API KEY KURULUM
# Kendi API key'inizi Hermes'e güvenli şekilde ekler

echo "════════════════════════════════════════════════════════════════════════"
echo "🔑 ANTHROPIC API KEY KURULUM"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Hermes config dosyası
CONFIG_FILE="$HOME/.config/hermes/config.yaml"
BACKUP_FILE="$HOME/.config/hermes/config.yaml.backup.$(date +%Y%m%d_%H%M%S)"

echo "📁 Config dosyası: $CONFIG_FILE"
echo ""

# Backup oluştur
if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "$BACKUP_FILE"
    echo "✅ Yedek oluşturuldu: $BACKUP_FILE"
else
    echo "⚠️  Config dosyası bulunamadı, yeni oluşturulacak"
    mkdir -p "$(dirname "$CONFIG_FILE")"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "⚠️  ÖNEMLİ GÜVENLİK UYARISI"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "API Key'inizi GİRMEDEN ÖNCE:"
echo ""
echo "1. ✅ console.anthropic.com'da yeni key oluşturun"
echo "2. ✅ Eski key'i (sk-ant-usr-18FApX...) SİLİN"
echo "3. ✅ Yeni key'i kopyalayın (sk-ant-... ile başlar)"
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo ""
read -p "🔑 Yeni Anthropic API Key'inizi yapıştırın: " API_KEY

# Doğrulama
if [[ ! $API_KEY =~ ^sk-ant- ]]; then
    echo ""
    echo "❌ HATA: Geçersiz API key formatı!"
    echo "   Anthropic key'leri 'sk-ant-' ile başlamalı"
    echo ""
    exit 1
fi

echo ""
echo "📝 Config dosyasına ekleniyor..."

# Config dosyasında anthropic bölümü var mı kontrol et
if grep -q "^anthropic:" "$CONFIG_FILE" 2>/dev/null; then
    # Var, güncelle
    sed -i.bak "s|api_key:.*|api_key: \"$API_KEY\"|" "$CONFIG_FILE"
    echo "   ✅ Mevcut anthropic config güncellendi"
else
    # Yok, ekle
    cat >> "$CONFIG_FILE" << EOF

# Anthropic API Configuration
anthropic:
  api_key: "$API_KEY"
  # model: claude-sonnet-4-5-20250929  # Varsayılan model
EOF
    echo "   ✅ Yeni anthropic config eklendi"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "✅ KURULUM TAMAMLANDI"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "📋 Yapılanlar:"
echo "   1. ✅ Config yedeklendi"
echo "   2. ✅ API key config'e eklendi"
echo ""
echo "🔄 Şimdi yapmanız gerekenler:"
echo "   1. Hermes'i restart edin (pencereyi kapat/aç)"
echo "   2. Test edin: 'Merhaba, ben Claude' yazın"
echo ""
echo "🔍 Config dosyasını görmek için:"
echo "   cat $CONFIG_FILE"
echo ""
echo "════════════════════════════════════════════════════════════════════════"
