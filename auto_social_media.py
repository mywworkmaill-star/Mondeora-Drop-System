#!/usr/bin/env python
"""
AUTOMATIC SOCIAL MEDIA POSTER
Posts to Facebook, Reddit, Twitter automatically - NO MANUAL WORK!
"""

import sys
import os
sys.path.insert(0, '.')

import time
import json
from datetime import datetime

class SocialMediaAutoPoster:
    """
    Fully automated social media posting
    """
    
    def __init__(self):
        self.content = self.load_viral_content()
        self.results = {
            'facebook': [],
            'reddit': [],
            'twitter': [],
            'instagram': []
        }
        
    def load_viral_content(self):
        """Load pre-generated content"""
        with open('viral_content/facebook_viral_post.txt', 'r', encoding='utf-8') as f:
            facebook = f.read()
            
        with open('viral_content/reddit_posts.txt', 'r', encoding='utf-8') as f:
            reddit = f.read()
            
        return {
            'facebook': facebook,
            'reddit': reddit
        }
    
    def post_to_reddit(self):
        """
        Automatic Reddit posting using PRAW
        """
        print("=" * 70)
        print("🤖 REDDIT AUTO-POSTER")
        print("=" * 70)
        print()
        
        try:
            import praw
            
            # Reddit API credentials (user needs to provide)
            reddit = praw.Reddit(
                client_id=os.getenv('REDDIT_CLIENT_ID'),
                client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
                user_agent=os.getenv('REDDIT_USER_AGENT'),
                username=os.getenv('REDDIT_USERNAME'),
                password=os.getenv('REDDIT_PASSWORD')
            )
            
            # Post to r/de
            print("📝 Posting to r/de...")
            subreddit_de = reddit.subreddit('de')
            
            post_de = subreddit_de.submit(
                title="[DEAL] Premium Haustier-Spielzeug auf eBay.de - 50% günstiger als Fressnapf",
                selftext="""Hallo zusammen,

wollte nur kurz teilen: Ich habe letzte Woche Haustier-Spielzeug bei Fressnapf angeschaut (€25-35 pro Stück) und dann aus Neugier auf eBay.de nachgeschaut.

Exakt die gleichen Produkte für €15-18. HALB so teuer!

Falls jemand Haustiere hat und sparen möchte, lohnt sich ein Blick auf eBay.de in der Kategorie "Haustierbedarf".

Qualität ist 1:1 die gleiche (habe beide verglichen).

Viel Erfolg beim Sparen!"""
            )
            
            print(f"✅ Posted to r/de: {post_de.url}")
            self.results['reddit'].append(f"r/de: {post_de.url}")
            
            time.sleep(5)  # Rate limit
            
            # Post to r/Haustiere
            print("📝 Posting to r/Haustiere...")
            subreddit_pets = reddit.subreddit('Haustiere')
            
            post_pets = subreddit_pets.submit(
                title="Gute & günstige Haustier-Spielzeuge - Wo kauft ihr ein?",
                selftext="""Hey Leute,

ich hab lange nach guten aber bezahlbaren Spielzeugen für meine Katze/Hund gesucht.

Nach viel Recherche: eBay.de hat überraschend gute Deals. Oft 40-60% günstiger als Zoohandlungen.

Qualität ist gut (nutze sie seit 2 Wochen, keine Probleme).

Falls jemand Empfehlungen braucht, kann ich ein paar Links teilen.

Was sind eure Erfahrungen? Wo kauft ihr ein?"""
            )
            
            print(f"✅ Posted to r/Haustiere: {post_pets.url}")
            self.results['reddit'].append(f"r/Haustiere: {post_pets.url}")
            
            print()
            print("✅ Reddit auto-posting COMPLETE!")
            return True
            
        except ImportError:
            print("⚠️  PRAW not installed")
            print("   Install: pip install praw")
            return False
            
        except Exception as e:
            print(f"❌ Reddit error: {e}")
            print()
            print("🔧 SETUP NEEDED:")
            print("   1. Go to: https://www.reddit.com/prefs/apps")
            print("   2. Create app (script type)")
            print("   3. Get client_id & client_secret")
            print("   4. Add to .env:")
            print("      REDDIT_CLIENT_ID=...")
            print("      REDDIT_CLIENT_SECRET=...")
            print("      REDDIT_USERNAME=...")
            print("      REDDIT_PASSWORD=...")
            print("      REDDIT_USER_AGENT=...")
            return False
    
    def post_to_facebook(self):
        """
        Automatic Facebook group posting
        """
        print("=" * 70)
        print("🤖 FACEBOOK AUTO-POSTER")
        print("=" * 70)
        print()
        
        try:
            import requests
            
            # Facebook Graph API
            access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
            
            if not access_token:
                raise ValueError("No Facebook access token")
            
            # Facebook groups to post to
            groups = {
                'Hunde Besitzer Deutschland': os.getenv('FB_GROUP_1_ID'),
                'Katzen Fans Deutschland': os.getenv('FB_GROUP_2_ID'),
                'Haustiere Deutschland': os.getenv('FB_GROUP_3_ID'),
                'eBay Kleinanzeigen Haustiere': os.getenv('FB_GROUP_4_ID'),
                'Pet Lovers Germany': os.getenv('FB_GROUP_5_ID')
            }
            
            post_text = """🐾 MEGA PET TOY HAUL - NUR BEI EBAY.DE! 🐾

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

🚚 Kostenloser Versand in ganz Deutschland
⭐ Top Qualität (habe selbst getestet!)
🐶🐱 Perfekt für Hunde & Katzen

⚠️ NUR NOCH WENIGE AUF LAGER! ⚠️

Wer Interesse hat, schreibt mir eine PM für den Link!

#Haustiere #Hund #Katze #Schnäppchen #Deutschland"""
            
            for group_name, group_id in groups.items():
                if not group_id:
                    print(f"⏭️  Skipping {group_name} (no ID)")
                    continue
                
                print(f"📝 Posting to {group_name}...")
                
                url = f"https://graph.facebook.com/{group_id}/feed"
                
                data = {
                    'message': post_text,
                    'access_token': access_token
                }
                
                response = requests.post(url, data=data, timeout=30)
                
                if response.status_code == 200:
                    post_id = response.json().get('id')
                    print(f"✅ Posted: {post_id}")
                    self.results['facebook'].append(f"{group_name}: {post_id}")
                else:
                    print(f"❌ Failed: {response.text}")
                
                time.sleep(3)  # Rate limit
            
            print()
            print("✅ Facebook auto-posting COMPLETE!")
            return True
            
        except Exception as e:
            print(f"❌ Facebook error: {e}")
            print()
            print("🔧 SETUP NEEDED:")
            print("   1. Go to: https://developers.facebook.com")
            print("   2. Create app")
            print("   3. Get access token (user_posts, publish_to_groups)")
            print("   4. Get group IDs from Facebook URLs")
            print("   5. Add to .env:")
            print("      FACEBOOK_ACCESS_TOKEN=...")
            print("      FB_GROUP_1_ID=...")
            print("      FB_GROUP_2_ID=...")
            return False
    
    def post_to_twitter(self):
        """
        Automatic Twitter posting
        """
        print("=" * 70)
        print("🤖 TWITTER AUTO-POSTER")
        print("=" * 70)
        print()
        
        try:
            import tweepy
            
            # Twitter API v2
            client = tweepy.Client(
                consumer_key=os.getenv('TWITTER_API_KEY'),
                consumer_secret=os.getenv('TWITTER_API_SECRET'),
                access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
                access_token_secret=os.getenv('TWITTER_ACCESS_SECRET')
            )
            
            tweet_text = """🐾 FLASH SALE! 🐾

Haustier Spielzeug - 15% RABATT
Kostenloser Versand 🇩🇪
NUR HEUTE!

Katzen 🐱 Hunde 🐶 Alle Haustiere

eBay.de - Link in Bio

#Haustiere #PetDeals #FlashSale #Germany"""
            
            print("📝 Posting tweet...")
            response = client.create_tweet(text=tweet_text)
            
            tweet_id = response.data['id']
            print(f"✅ Tweeted: https://twitter.com/user/status/{tweet_id}")
            self.results['twitter'].append(f"Tweet: {tweet_id}")
            
            print()
            print("✅ Twitter auto-posting COMPLETE!")
            return True
            
        except ImportError:
            print("⚠️  Tweepy not installed")
            print("   Install: pip install tweepy")
            return False
            
        except Exception as e:
            print(f"❌ Twitter error: {e}")
            print()
            print("🔧 SETUP NEEDED:")
            print("   1. Go to: https://developer.twitter.com")
            print("   2. Create app")
            print("   3. Get API keys")
            print("   4. Add to .env:")
            print("      TWITTER_API_KEY=...")
            print("      TWITTER_API_SECRET=...")
            print("      TWITTER_ACCESS_TOKEN=...")
            print("      TWITTER_ACCESS_SECRET=...")
            return False
    
    def run_automation(self):
        """
        Run full social media automation
        """
        print("=" * 70)
        print("🚀 SOCIAL MEDIA AUTO-POSTER - STARTING...")
        print("=" * 70)
        print()
        print("⚡ FULLY AUTOMATED - NO MANUAL WORK!")
        print()
        
        # Post to all platforms
        reddit_success = self.post_to_reddit()
        time.sleep(2)
        
        facebook_success = self.post_to_facebook()
        time.sleep(2)
        
        twitter_success = self.post_to_twitter()
        
        # Summary
        print()
        print("=" * 70)
        print("📊 AUTOMATION RESULTS")
        print("=" * 70)
        print()
        print(f"Reddit:     {'✅ SUCCESS' if reddit_success else '❌ SETUP NEEDED'}")
        print(f"Facebook:   {'✅ SUCCESS' if facebook_success else '❌ SETUP NEEDED'}")
        print(f"Twitter:    {'✅ SUCCESS' if twitter_success else '❌ SETUP NEEDED'}")
        print()
        
        if reddit_success or facebook_success or twitter_success:
            print("✅ At least one platform posted successfully!")
            print()
            print("📊 Posted content:")
            
            if self.results['reddit']:
                print("\nReddit:")
                for post in self.results['reddit']:
                    print(f"  • {post}")
            
            if self.results['facebook']:
                print("\nFacebook:")
                for post in self.results['facebook']:
                    print(f"  • {post}")
            
            if self.results['twitter']:
                print("\nTwitter:")
                for post in self.results['twitter']:
                    print(f"  • {post}")
        else:
            print("⚠️  All platforms need API setup")
            print()
            print("📋 QUICK SETUP GUIDE:")
            print()
            print("1. Install dependencies:")
            print("   pip install praw tweepy requests")
            print()
            print("2. Get API credentials (see error messages above)")
            print()
            print("3. Add to .env file")
            print()
            print("4. Run again: python auto_social_media.py")
        
        print()
        
        # Save results
        with open('automation_results.json', 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': self.results,
                'success': {
                    'reddit': reddit_success,
                    'facebook': facebook_success,
                    'twitter': twitter_success
                }
            }, f, indent=2)
        
        print("💾 Results saved to: automation_results.json")
        print()

if __name__ == "__main__":
    try:
        poster = SocialMediaAutoPoster()
        poster.run_automation()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
