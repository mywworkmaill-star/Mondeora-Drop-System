# Ultra Dependencies Installation Script
# Run: bash install_ultra_deps.sh

echo "🚀 Installing ULTRA dependencies..."

# AI/ML Libraries
pip install openai anthropic scikit-learn numpy pandas

# Analytics & Dashboard
pip install plotly dash dash-bootstrap-components

# Image Processing
pip install pillow reportlab

# Web Scraping & Automation
pip install beautifulsoup4 selenium playwright
playwright install chromium

# Social Media APIs
pip install instagrapi TikTokApi tweepy

# Email Marketing
pip install sendgrid

# Financial
pip install stripe python-dateutil

# Multi-Platform E-commerce
# pip install sp-api  # Amazon Selling Partner API
# pip install shopify-python-api
# pip install python-etsy

# Performance
pip install redis celery

# Utilities
pip install python-dotenv requests schedule asyncio aiohttp

echo "✅ Installation complete!"
echo "Next: Configure API keys in .env"
