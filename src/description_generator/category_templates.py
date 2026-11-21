"""
Category-Specific Templates
Different HTML content for different product categories
"""

class CategoryTemplates:
    """Category-aware description templates"""
    
    @staticmethod
    def detect_category(title, aspects=None):
        """
        Detect product category from title and aspects
        
        Returns: category name (string)
        """
        title_lower = title.lower()
        
        # Category detection patterns
        if any(word in title_lower for word in ['handtuch', 'towel', 'tuch']):
            return 'towel_holder'
        elif any(word in title_lower for word in ['kabel', 'cable', 'organizer', 'binder']):
            return 'cable_organizer'
        elif any(word in title_lower for word in ['küche', 'kitchen', 'kochen']):
            return 'kitchen_storage'
        elif any(word in title_lower for word in ['bad', 'bathroom', 'waschbecken']):
            return 'bathroom_storage'
        elif any(word in title_lower for word in ['werkzeug', 'tool', 'schrauben']):
            return 'tool_storage'
        elif any(word in title_lower for word in ['aufbewahrung', 'storage', 'box', 'behälter']):
            return 'general_storage'
        else:
            return 'general'
    
    @staticmethod
    def generate_category_content(category, product_data):
        """Generate category-specific HTML content"""
        
        generators = {
            'towel_holder': CategoryTemplates._towel_holder,
            'cable_organizer': CategoryTemplates._cable_organizer,
            'kitchen_storage': CategoryTemplates._kitchen_storage,
            'bathroom_storage': CategoryTemplates._bathroom_storage,
            'tool_storage': CategoryTemplates._tool_storage,
            'general_storage': CategoryTemplates._general_storage,
            'general': CategoryTemplates._general
        }
        
        generator = generators.get(category, CategoryTemplates._general)
        return generator(product_data)
    
    @staticmethod
    def _towel_holder(product_data):
        """Paper towel / tissue holder description"""
        return '''
<p style="line-height: 1.8;">
Dieser praktische Halter ist die perfekte Lösung für die Aufbewahrung von 
Papierhandtüchern, Tissue oder Toilettenpapier. Die selbstklebende Montage 
ermöglicht eine werkzeugfreie Installation in Küche, Bad oder WC.
</p>

<p style="line-height: 1.8;">
Das robuste Design hält sicher an glatten Oberflächen und bietet einfachen Zugriff 
auf Papierrollen. Ideal für Küche, Badezimmer, Gäste-WC oder Waschküche.
</p>
'''
    
    @staticmethod
    def _cable_organizer(product_data):
        """Cable organizer / cable management"""
        return '''
<p style="line-height: 1.8;">
Dieser praktische Kabelorganizer ist die perfekte Lösung für die ordentliche 
Aufbewahrung von Kabelbindern, Kabeln und Kleinteilen. Das kompakte Design 
ermöglicht platzsparende Lagerung in Schubladen oder Werkzeugkisten.
</p>

<p style="line-height: 1.8;">
Die langlebige Konstruktion aus hochwertigem Kunststoff garantiert eine sichere 
Aufbewahrung. Ideal für Werkstatt, Büro, Zuhause oder unterwegs.
</p>
'''
    
    @staticmethod
    def _kitchen_storage(product_data):
        """Kitchen storage / organization"""
        return '''
<p style="line-height: 1.8;">
Dieser praktische Küchenorganizer bietet effiziente Aufbewahrungslösung für 
Küchenutensilien, Gewürze oder Lebensmittel. Das durchdachte Design maximiert 
den verfügbaren Stauraum und sorgt für Ordnung.
</p>

<p style="line-height: 1.8;">
Die robuste Konstruktion garantiert lange Haltbarkeit. Perfekt für Küchenschränke, 
Arbeitsplatten oder Speisekammer. Leicht zu reinigen und zu pflegen.
</p>
'''
    
    @staticmethod
    def _bathroom_storage(product_data):
        """Bathroom storage / organization"""
        return '''
<p style="line-height: 1.8;">
Dieser praktische Badorganizer bietet clevere Aufbewahrungslösung für 
Kosmetikartikel, Handtücher oder Badutensilien. Das platzsparende Design 
nutzt den verfügbaren Raum optimal aus.
</p>

<p style="line-height: 1.8;">
Die feuchtigkeitsbeständige Konstruktion eignet sich perfekt für Badezimmer. 
Einfache Montage und Reinigung. Ideal für kleine und große Bäder.
</p>
'''
    
    @staticmethod
    def _tool_storage(product_data):
        """Tool storage / workshop organization"""
        return '''
<p style="line-height: 1.8;">
Dieser robuste Werkzeugorganizer bietet professionelle Aufbewahrungslösung für 
Werkzeuge, Schrauben und Kleinteile. Das stabile Design garantiert sicheren Halt 
und einfachen Zugriff.
</p>

<p style="line-height: 1.8;">
Die langlebige Konstruktion hält den Belastungen in Werkstatt stand. Perfekt für 
Heimwerker und Profis. Sorgt für Ordnung am Arbeitsplatz.
</p>
'''
    
    @staticmethod
    def _general_storage(product_data):
        """General storage / organization"""
        return '''
<p style="line-height: 1.8;">
Dieser vielseitige Organizer bietet praktische Aufbewahrungslösung für verschiedene 
Gegenstände. Das durchdachte Design kombiniert Funktionalität mit platzsparendem Aufbau.
</p>

<p style="line-height: 1.8;">
Die robuste Konstruktion garantiert lange Nutzungsdauer. Perfekt für Zuhause, Büro 
oder unterwegs. Sorgt für Ordnung und übersichtliche Aufbewahrung.
</p>
'''
    
    @staticmethod
    def _general(product_data):
        """Generic fallback template"""
        title = product_data.get('title', 'Produkt')
        
        return f'''
<p style="line-height: 1.8;">
Dieses hochwertige Produkt bietet praktische Lösung für den täglichen Gebrauch. 
Das durchdachte Design kombiniert Funktionalität mit ansprechendem Aussehen.
</p>

<p style="line-height: 1.8;">
Die robuste Konstruktion garantiert lange Haltbarkeit und zuverlässige Nutzung. 
Perfekt für verschiedene Einsatzbereiche. Einfach zu verwenden und zu pflegen.
</p>
'''
