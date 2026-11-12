#!/usr/bin/env python
"""
SELENIUM BROWSER AUTOMATION - SOCIAL MEDIA AUTO-POSTER
NO API KEYS NEEDED! Uses real browser to post automatically.
"""

import sys
import os
sys.path.insert(0, '.')

import time
from datetime import datetime

class BrowserAutoPoster:
    """
    Automated social media posting using Selenium (real browser)
    NO API keys required!
    """
    
    def __init__(self):
        self.driver = None
        self.results = []
        
    def setup_browser(self):
        """Initialize Selenium browser"""
        print("🌐 Starting browser...")
        
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            # options.add_argument('--headless')  # Uncomment for invisible mode
            options.add_argument('--disable-bots')
            options.add_argument('--start-maximized')
            
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 10)
            
            print("✅ Browser ready!")
            return True
            
        except ImportError:
            print("❌ Selenium not installed")
            print("   Install: pip install selenium")
            print("   Also install ChromeDriver:")
            print("   https://chromedriver.chromium.org/downloads")
            return False
        except Exception as e:
            print(f"❌ Browser error: {e}")
            return False
    
    def post_to_reddit(self, subreddit, title, text):
        """
        Post to Reddit automatically
        """
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            print(f"\n📝 Posting to r/{subreddit}...")
            
            # Go to Reddit
            self.driver.get(f'https://www.reddit.com/r/{subreddit}/submit')
            time.sleep(2)
            
            # Check if logged in
            if 'login' in self.driver.current_url:
                print("⚠️  Not logged in to Reddit")
                print("   Please login manually in the browser...")
                print("   Waiting 60 seconds for manual login...")
                time.sleep(60)
                
                # Try again
                self.driver.get(f'https://www.reddit.com/r/{subreddit}/submit')
                time.sleep(2)
            
            # Click "Post" tab (text post)
            try:
                post_tab = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Post')]"))
                )
                post_tab.click()
                time.sleep(1)
            except:
                print("   Already on post page")
            
            # Fill title
            title_field = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//textarea[@placeholder='Title']"))
            )
            title_field.send_keys(title)
            time.sleep(0.5)
            
            # Fill text
            text_field = self.driver.find_element(By.XPATH, "//div[@contenteditable='true']")
            text_field.send_keys(text)
            time.sleep(1)
            
            # Click Post button
            post_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Post')]")
            post_button.click()
            
            print(f"✅ Posted to r/{subreddit}!")
            self.results.append(f"Reddit r/{subreddit}: SUCCESS")
            
            time.sleep(3)
            return True
            
        except Exception as e:
            print(f"❌ Failed to post to r/{subreddit}: {e}")
            self.results.append(f"Reddit r/{subreddit}: FAILED")
            return False
    
    def post_to_facebook_group(self, group_name, text):
        """
        Post to Facebook group automatically
        """
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            print(f"\n📝 Posting to Facebook: {group_name}...")
            
            # Search for group
            self.driver.get('https://www.facebook.com/groups/search/')
            time.sleep(2)
            
            # Check if logged in
            if 'login' in self.driver.current_url:
                print("⚠️  Not logged in to Facebook")
                print("   Please login manually in the browser...")
                print("   Waiting 60 seconds for manual login...")
                time.sleep(60)
            
            # Search for group
            search_box = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='search']"))
            )
            search_box.send_keys(group_name)
            search_box.send_keys('\n')
            time.sleep(3)
            
            # Click first group result
            first_group = self.driver.find_element(By.XPATH, "//a[contains(@href, '/groups/')]")
            first_group.click()
            time.sleep(3)
            
            # Click "Write something" box
            write_box = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Write something')]"))
            )
            write_box.click()
            time.sleep(2)
            
            # Type post content
            text_area = self.driver.find_element(By.XPATH, "//div[@contenteditable='true']")
            text_area.send_keys(text)
            time.sleep(2)
            
            # Click Post button
            post_button = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Post')]")
            post_button.click()
            
            print(f"✅ Posted to Facebook: {group_name}!")
            self.results.append(f"Facebook {group_name}: SUCCESS")
            
            time.sleep(5)
            return True
            
        except Exception as e:
            print(f"❌ Failed to post to Facebook {group_name}: {e}")
            self.results.append(f"Facebook {group_name}: FAILED")
            return False
    
    def run_full_automation(self):
        """
        Run complete automated posting
        """
        print("=" * 70)
        print("🤖 BROWSER AUTO-POSTER - STARTING...")
        print("=" * 70)
        print()
        print("⚡ NO API KEYS NEEDED!")
        print("🌐 Uses real browser (you'll see it working)")
        print()
        
        if not self.setup_browser():
            return
        
        try:
            # Reddit posts
            print("\n" + "=" * 70)
            print("📱 REDDIT AUTO-POSTING")
            print("=" * 70)
            
            self.post_to_reddit(
                subreddit='de',
                title='[DEAL] Premium Haustier-Spielzeug auf eBay.de - 50% günstiger als Fressnapf',
                text="""Hallo zusammen,

wollte nur kurz teilen: Ich habe letzte Woche Haustier-Spielzeug bei Fressnapf angeschaut (€25-35 pro Stück) und dann aus Neugier auf eBay.de nachgeschaut.

Exakt die gleichen Produkte für €15-18. HALB so teuer!

Falls jemand Haustiere hat und sparen möchte, lohnt sich ein Blick auf eBay.de in der Kategorie "Haustierbedarf".

Qualität ist 1:1 die gleiche (habe beide verglichen).

Viel Erfolg beim Sparen!"""
            )
            
            time.sleep(5)
            
            self.post_to_reddit(
                subreddit='Haustiere',
                title='Gute & günstige Haustier-Spielzeuge - Wo kauft ihr ein?',
                text="""Hey Leute,

ich hab lange nach guten aber bezahlbaren Spielzeugen für meine Katze/Hund gesucht.

Nach viel Recherche: eBay.de hat überraschend gute Deals. Oft 40-60% günstiger als Zoohandlungen.

Qualität ist gut (nutze sie seit 2 Wochen, keine Probleme).

Falls jemand Empfehlungen braucht, kann ich ein paar Links teilen.

Was sind eure Erfahrungen? Wo kauft ihr ein?"""
            )
            
            # Facebook posts
            print("\n" + "=" * 70)
            print("📘 FACEBOOK AUTO-POSTING")
            print("=" * 70)
            
            facebook_text = """🐾 MEGA PET TOY HAUL - NUR BEI EBAY.DE! 🐾

Ich habe gerade 5 PREMIUM Haustier-Spielzeuge für meine Lieblinge gekauft und wollte diese unglaublichen Deals mit euch teilen! 🎉

💰 NORMALE PREISE (Fressnapf/Zooplus): ~€323
✨ MEIN PREIS (eBay.de): €161
🎯 ERSPARNIS: €161+ (50%!)

Was ich bekommen habe:
1. Haustier-Fingerzahnbürste - €31.08
2. Hundespielzeugball - €31.78
3. Katzenminze Spielzeug - €31.43
4. Katze Puzzle Spielzeug - €34.98
5. Pop-Up Maus - €32.04

🚚 Kostenloser Versand
⭐ Top Qualität
🐶🐱 Perfekt für Hunde & Katzen

⚠️ NUR NOCH WENIGE AUF LAGER! ⚠️

Wer Interesse hat, PM für Link!

#Haustiere #Hund #Katze #Schnäppchen"""
            
            facebook_groups = [
                'Hunde Besitzer Deutschland',
                'Katzen Fans Deutschland',
                'Haustiere Deutschland'
            ]
            
            for group in facebook_groups:
                self.post_to_facebook_group(group, facebook_text)
                time.sleep(5)
            
        except Exception as e:
            print(f"\n❌ Automation error: {e}")
        
        finally:
            # Summary
            print("\n" + "=" * 70)
            print("📊 AUTOMATION RESULTS")
            print("=" * 70)
            print()
            
            for result in self.results:
                print(f"  • {result}")
            
            print()
            print("✅ Automation complete!")
            print()
            print("⏸️  Browser will close in 10 seconds...")
            print("   (Press Ctrl+C to keep it open)")
            
            try:
                time.sleep(10)
            except KeyboardInterrupt:
                print("\n⏸️  Browser kept open")
                return
            
            if self.driver:
                self.driver.quit()
                print("Browser closed.")

if __name__ == "__main__":
    try:
        poster = BrowserAutoPoster()
        poster.run_full_automation()
        
    except KeyboardInterrupt:
        print("\n\n⏸️  Automation stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
