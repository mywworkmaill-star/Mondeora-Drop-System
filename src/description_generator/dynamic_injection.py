"""
Dynamic Product Data Injection
Extracts and formats product data for template insertion
"""

import json

class DynamicInjector:
    """Extract and format product data for templates"""
    
    @staticmethod
    def prepare_product_data(product_dict):
        """
        Extract and format product data from database row
        
        Args:
            product_dict: Dict from database with all product fields
            
        Returns:
            dict: Formatted data ready for template injection
        """
        
        # Parse aspects
        aspects = {}
        if product_dict.get('aspects'):
            try:
                aspects = json.loads(product_dict['aspects'])
            except:
                aspects = {}
        
        # Extract dimensions
        dimensions = {}
        for dim_key in ['Länge', 'Breite', 'Höhe', 'Durchmesser', 'Gewicht', 'Kapazität']:
            if dim_key in aspects:
                value = aspects[dim_key]
                if isinstance(value, list):
                    value = value[0] if value else ''
                # Skip "Siehe Beschreibung"
                if value and 'Siehe Beschreibung' not in value:
                    dimensions[dim_key] = value
        
        # Add material and color
        if 'Material' in aspects or 'Hauptmaterial' in aspects:
            mat = aspects.get('Material') or aspects.get('Hauptmaterial', '')
            if isinstance(mat, list):
                mat = mat[0] if mat else 'Kunststoff'
            dimensions['Material'] = mat if mat else 'Kunststoff'
        
        if 'Farbe' in aspects:
            color = aspects.get('Farbe', '')
            if isinstance(color, list):
                color = color[0] if color else 'Mehrfarbig'
            dimensions['Farbe'] = color if color else 'Mehrfarbig'
        
        if 'Form' in aspects:
            form = aspects.get('Form', '')
            if isinstance(form, list):
                form = form[0] if form else ''
            if form:
                dimensions['Form'] = form
        
        # Build highlights
        highlights = []
        
        # Material highlight
        material = dimensions.get('Material', 'Kunststoff')
        highlights.append(f'<strong>Material:</strong> {material}')
        
        # Color highlight  
        color = dimensions.get('Farbe', 'Mehrfarbig')
        highlights.append(f'<strong>Farbe:</strong> {color}')
        
        # Dimension highlight
        if 'Länge' in dimensions and 'Breite' in dimensions:
            laenge = dimensions['Länge']
            breite = dimensions['Breite']
            highlights.append(f'<strong>Maße:</strong> {laenge} x {breite}')
        
        # Features from aspects
        if 'Besonderheiten' in aspects:
            features = aspects['Besonderheiten']
            if isinstance(features, list):
                for feat in features[:2]:  # Max 2
                    highlights.append(f'<strong>Feature:</strong> {feat}')
            elif isinstance(features, str):
                highlights.append(f'<strong>Feature:</strong> {features}')
        
        # Room/Application
        if 'Zimmer' in aspects:
            room = aspects['Zimmer']
            if isinstance(room, list):
                room = room[0]
            highlights.append(f'<strong>Ideal für:</strong> {room}')
        
        # Build applications list
        applications = []
        if 'Zimmer' in aspects:
            room = aspects['Zimmer']
            if isinstance(room, list):
                room = room[0] if room else ''
            if room:
                applications.append(room)
        
        # Add generic applications based on category
        title = product_dict.get('title', '')
        if 'küche' in title.lower() or 'kitchen' in title.lower():
            applications.extend(['Küche', 'Speisekammer'])
        elif 'bad' in title.lower() or 'bathroom' in title.lower():
            applications.extend(['Badezimmer', 'Gäste-WC'])
        elif 'werkzeug' in title.lower() or 'tool' in title.lower():
            applications.extend(['Werkstatt', 'Garage'])
        
        # Deduplicate
        applications = list(dict.fromkeys(applications))[:4]  # Max 4
        
        # Compile full data
        data = {
            'title': product_dict.get('title', 'Produkt')[:60],  # Truncate long titles
            'highlights': highlights[:5],  # Max 5
            'dimensions': dimensions,
            'material': dimensions.get('Material', 'Kunststoff'),
            'color': dimensions.get('Farbe', 'Mehrfarbig'),
            'features': [],
            'applications': applications if applications else ['Zuhause', 'Büro']
        }
        
        return data
