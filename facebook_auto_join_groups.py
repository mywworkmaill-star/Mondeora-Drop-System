#!/usr/bin/env python
"""
FACEBOOK AUTO-JOIN GROUPS
Automatically joins/requests to join Facebook groups
"""

import time
import os
from datetime import datetime

def facebook_auto_join():
    """
    Automatically join Facebook groups
    """
    print("=" * 70)
    print("🔵 FACEBOOK AUTO-JOIN GROUPS - STARTING...")
    print("=" * 70)
    print()
    
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.edge.service import Service
        from selenium.webdriver.common.keys import Keys
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        
        print("🌐 Setting up Microsoft Edge browser...")
        
        # Setup Edge
        service = Service(EdgeChromiumDriverManager().install())
        options = webdriver.EdgeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        driver = webdriver.Edge(service=service, options=options)
        wait = WebDriverWait(driver, 20)
        
        print("✅ Browser ready!")
        print()
        
        # Groups to join
        group_searches = [
            "Haustiere Deutschland",
            "Hunde Deutschland",
            "Katzen Deutschland",
            "Pet Lovers Germany",
            "Hunde Besitzer Deutschland",
            "Katzen Fans Deutschland",
            "Haustier Zubehör Deutschland",
            "Hundespielzeug Deutschland"
        ]
        
        # Go to Facebook
        print("🔵 Opening Facebook...")
        driver.get('https://www.facebook.com')
        time.sleep(3)
        
        # Check if logged in
        if 'login' in driver.current_url or 'Log In' in driver.page_source:
            print()
            print("=" * 70)
            print("⚠️  FACEBOOK LOGIN REQUIRED")
            print("=" * 70)
            print()
            print("Please login to Facebook in the browser window...")
            print("Waiting 120 seconds for you to login...")
            print()
            print("Steps:")
            print("  1. Enter email/phone")
            print("  2. Enter password")
            print("  3. Click 'Log In'")
            print("  4. Wait for home page to load")
            print()
            
            time.sleep(120)
        
        print("✅ Logged in to Facebook!")
        print()
        
        # Join each group
        joined_groups = 0
        
        for i, group_search in enumerate(group_searches, 1):
            print("=" * 70)
            print(f"🔍 SEARCHING {i}/{len(group_searches)}: {group_search}")
            print("=" * 70)
            print()
            
            try:
                # Search for group
                print(f"Searching: {group_search}...")
                search_url = f'https://www.facebook.com/search/groups/?q={group_search.replace(" ", "%20")}'
                driver.get(search_url)
                time.sleep(5)
                
                print("Looking for groups...")
                
                # Find group links
                group_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/groups/')]")
                
                if not group_links:
                    print(f"⚠️  No groups found for: {group_search}")
                    print()
                    continue
                
                # Try to join first 3 groups in search results
                groups_joined_this_search = 0
                
                for j in range(min(3, len(group_links))):
                    try:
                        print(f"   Trying group {j+1}...")
                        
                        # Re-search to avoid stale elements
                        driver.get(search_url)
                        time.sleep(3)
                        
                        group_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/groups/')]")
                        if j >= len(group_links):
                            continue
                        
                        # Get group URL
                        group_url = group_links[j].get_attribute('href')
                        
                        # Visit group
                        driver.get(group_url)
                        time.sleep(4)
                        
                        # Look for Join/Beitreten button
                        join_buttons = []
                        
                        # Method 1: Text "Join" or "Beitreten"
                        join_buttons = driver.find_elements(By.XPATH, 
                            "//span[text()='Join' or text()='Beitreten' or text()='Join Group' or text()='Gruppe beitreten']")
                        
                        if not join_buttons:
                            # Method 2: aria-label
                            join_buttons = driver.find_elements(By.XPATH,
                                "//div[@aria-label='Join' or @aria-label='Beitreten' or @aria-label='Join Group']")
                        
                        if not join_buttons:
                            # Method 3: Check if already member
                            member_text = driver.page_source
                            if 'Joined' in member_text or 'Mitglied' in member_text:
                                print(f"   ✅ Already member of this group!")
                                groups_joined_this_search += 1
                                continue
                            else:
                                print(f"   ⚠️  Could not find join button (may need approval or already member)")
                                continue
                        
                        # Click join button
                        join_buttons[0].click()
                        time.sleep(2)
                        
                        # Check for confirmation popup (group questions, etc.)
                        try:
                            # Look for "Done" or "Fertig" button
                            done_buttons = driver.find_elements(By.XPATH,
                                "//span[text()='Done' or text()='Fertig' or text()='Submit']")
                            
                            if done_buttons:
                                # If there are questions, just click Done (they're usually optional)
                                done_buttons[0].click()
                                time.sleep(2)
                        except:
                            pass
                        
                        print(f"   ✅ Join request sent!")
                        joined_groups += 1
                        groups_joined_this_search += 1
                        
                        # Wait a bit to avoid spam detection
                        time.sleep(3)
                        
                    except Exception as e:
                        print(f"   ⚠️  Could not join group: {e}")
                        continue
                
                print(f"✅ Joined {groups_joined_this_search} groups for search: {group_search}")
                print()
                
                # Wait between searches
                if i < len(group_searches):
                    wait_time = 5
                    print(f"⏳ Waiting {wait_time} seconds before next search...")
                    time.sleep(wait_time)
                    print()
                
            except Exception as e:
                print(f"❌ Error searching for {group_search}: {e}")
                print()
                continue
        
        # Summary
        print()
        print("=" * 70)
        print("📊 AUTO-JOIN COMPLETE!")
        print("=" * 70)
        print()
        print(f"✅ Successfully joined/requested: {joined_groups} groups")
        print()
        print("📌 NEXT STEPS:")
        print("   1. Check Facebook notifications for group approvals")
        print("   2. Some groups are auto-approved (instant access)")
        print("   3. Others need admin approval (1-24 hours)")
        print("   4. Once approved, run facebook_auto_post_edge.py to post!")
        print()
        print("⏸️  Browser will close in 30 seconds...")
        print("   Press Ctrl+C to keep browser open and check groups")
        print()
        
        try:
            time.sleep(30)
        except KeyboardInterrupt:
            print("\n⏸️  Browser kept open - close manually when done")
            try:
                input("Press Enter to close browser...")
            except:
                time.sleep(60)
        
        driver.quit()
        print("✅ Done!")
        
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print()
        print("🔧 INSTALL:")
        print('   "C:/Program Files/Python311/python.exe" -m pip install selenium webdriver-manager')
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        import traceback
        traceback.print_exc()
        print()

if __name__ == "__main__":
    try:
        facebook_auto_join()
    except KeyboardInterrupt:
        print("\n\n⏸️  Stopped by user")
    except Exception as e:
        print(f"\n❌ Final error: {e}")
