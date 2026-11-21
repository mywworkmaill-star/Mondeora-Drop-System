"""
Length Optimizer
Ensures descriptions stay under eBay's 4000 character limit
"""

import re

class LengthOptimizer:
    """Optimize description length to fit eBay limits"""
    
    MAX_LENGTH = 4000
    TARGET_LENGTH = 3500
    
    @staticmethod
    def optimize(html, target=TARGET_LENGTH):
        """
        Optimize HTML to fit within target length
        
        Args:
            html: HTML string
            target: Target length (default 3500)
            
        Returns:
            str: Optimized HTML
        """
        
        current_length = len(html)
        
        if current_length <= target:
            return html  # Already good
        
        # Strategy 1: Remove extra whitespace
        html = re.sub(r'\n\s*\n', '\n', html)  # Remove empty lines
        html = re.sub(r'  +', ' ', html)  # Multiple spaces to single
        
        if len(html) <= target:
            return html
        
        # Strategy 2: Shorten padding in styles
        html = html.replace('padding: 15px', 'padding: 10px')
        html = html.replace('margin: 20px 0', 'margin: 15px 0')
        html = html.replace('margin: 15px 0', 'margin: 10px 0')
        
        if len(html) <= target:
            return html
        
        # Strategy 3: Remove emojis from headers
        html = re.sub(r'[✨📋🔧📦🚚⭐😊♻️🌟🏠💼🚗🔄]', '', html)
        
        if len(html) <= target:
            return html
        
        # Strategy 4: Simplify some sections
        # Remove the highlighted CTA section if needed
        if len(html) > target:
            # Find and remove the yellow highlight box
            pattern = r'<div style="background: #fff9c4.*?</div>\s*</div>'
            html = re.sub(pattern, '</div>', html, flags=re.DOTALL)
        
        if len(html) <= target:
            return html
        
        # Strategy 5: Last resort - truncate description paragraphs
        # This is aggressive but ensures we stay under limit
        if len(html) > target:
            # Find the product description section
            pattern = r'(<h2[^>]*>.*?Produktbeschreibung.*?</h2>)(.*?)(<h2)'
            match = re.search(pattern, html, re.DOTALL)
            
            if match:
                desc_content = match.group(2)
                # Shorten each paragraph
                shortened = re.sub(r'<p[^>]*>.*?</p>', 
                                   '<p style="line-height: 1.8;">Praktische Lösung für den täglichen Gebrauch.</p>', 
                                   desc_content, 
                                   count=1)
                html = html[:match.start(2)] + shortened + html[match.end(2):]
        
        return html[:LengthOptimizer.MAX_LENGTH - 100]  # Hard cut with safety margin
    
    @staticmethod
    def measure(html):
        """
        Measure HTML and return stats
        
        Returns:
            dict: {length, valid, over_target, margin}
        """
        length = len(html)
        
        return {
            'length': length,
            'valid': length <= LengthOptimizer.MAX_LENGTH,
            'over_target': length > LengthOptimizer.TARGET_LENGTH,
            'margin': LengthOptimizer.MAX_LENGTH - length,
            'percentage': round(length / LengthOptimizer.MAX_LENGTH * 100, 1)
        }
