"""
Base HTML Template for eBay Descriptions
Professional structure with placeholders for dynamic content
"""

class BaseTemplate:
    """Base template structure for all eBay descriptions"""
    
    # eBay API limit
    MAX_LENGTH = 4000
    TARGET_LENGTH = 3500  # Safe margin
    
    @staticmethod
    def generate(product_data, category_specific_html):
        """
        Generate complete description from product data and category-specific content
        
        Args:
            product_data: Dict with title, dimensions, material, color, features, etc.
            category_specific_html: HTML string for product-specific sections
            
        Returns:
            str: Complete HTML description under 4000 chars
        """
        
        title = product_data.get('title', 'Produkt')
        highlights = product_data.get('highlights', [])
        dimensions = product_data.get('dimensions', {})
        material = product_data.get('material', 'Kunststoff')
        color = product_data.get('color', 'Mehrfarbig')
        features = product_data.get('features', [])
        applications = product_data.get('applications', [])
        
        # Build highlights HTML
        highlights_html = ''
        if highlights:
            highlights_html = '<ul style="line-height: 1.8;">\n'
            for highlight in highlights[:5]:  # Max 5 highlights
                highlights_html += f'<li>{highlight}</li>\n'
            highlights_html += '</ul>'
        
        # Build dimensions table
        dim_rows = ''
        if dimensions:
            for key, value in dimensions.items():
                bg = ' style="background: #ecf0f1;"' if len(dim_rows.split('<tr')) % 2 == 0 else ''
                dim_rows += f'<tr{bg}>\n'
                dim_rows += f'<td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>{key}</strong></td>\n'
                dim_rows += f'<td style="padding: 8px; border: 1px solid #bdc3c7;">{value}</td>\n'
                dim_rows += '</tr>\n'
        
        # Build applications HTML
        applications_html = ''
        if applications:
            applications_html = '<div style="background: #e8f5e9; padding: 12px; border-radius: 5px; margin: 15px 0;">\n'
            applications_html += '<strong>Ideal für:</strong> ' + ', '.join(applications)
            applications_html += '\n</div>'
        
        # Assemble full HTML
        html = f'''
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">

<h1 style="color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px;">
{title}
</h1>

<div style="background: #ecf0f1; padding: 15px; margin: 20px 0; border-radius: 5px;">
<h3 style="color: #e74c3c; margin-top: 0;">✨ Highlights:</h3>
{highlights_html}
</div>

<h2 style="color: #2c3e50; border-left: 4px solid #3498db; padding-left: 10px;">
📋 Produktbeschreibung
</h2>

{category_specific_html}

<h2 style="color: #2c3e50; border-left: 4px solid #3498db; padding-left: 10px;">
🔧 Technische Daten
</h2>

<table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
{dim_rows}
</table>

{applications_html}

<h2 style="color: #2c3e50; border-left: 4px solid #3498db; padding-left: 10px;">
📦 Lieferumfang
</h2>

<p>1x {title[:50]}</p>

<h2 style="color: #2c3e50; border-left: 4px solid #3498db; padding-left: 10px;">
🚚 Versand
</h2>

<ul style="line-height: 1.8;">
<li>✅ Versand innerhalb 1-2 Werktagen</li>
<li>📦 Sichere Verpackung</li>
<li>🔄 30 Tage Rückgaberecht</li>
</ul>

<div style="background: #fff9c4; padding: 15px; text-align: center; border-radius: 5px; margin: 20px 0;">
<strong style="font-size: 18px;">⭐ Perfekt für Ordnung! ⭐</strong>
</div>

<div style="background: #263238; color: white; padding: 15px; text-align: center; border-radius: 5px;">
Bei Fragen kontaktieren Sie uns!<br>
<strong>Vielen Dank! 😊</strong>
</div>

</div>
'''
        
        # Remove extra whitespace
        html = html.strip()
        
        return html
    
    @staticmethod
    def validate_length(html):
        """Check if HTML is within eBay limits"""
        length = len(html)
        
        return {
            'valid': length <= BaseTemplate.MAX_LENGTH,
            'length': length,
            'max': BaseTemplate.MAX_LENGTH,
            'margin': BaseTemplate.MAX_LENGTH - length,
            'over_target': length > BaseTemplate.TARGET_LENGTH
        }
