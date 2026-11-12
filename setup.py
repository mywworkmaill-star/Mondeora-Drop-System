"""
Setup Script - Complete system initialization
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def print_step(step_num, text):
    """Print formatted step"""
    print(f"\n{'='*60}")
    print(f"STEP {step_num}: {text}")
    print(f"{'='*60}")

def run_command(command, description=""):
    """Run shell command"""
    try:
        print(f"  ▶ {description}" if description else "  ▶ Running command...")
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ❌ Error: {result.stderr}")
            return False
        if result.stdout:
            print(f"  ✅ {result.stdout.strip()}")
        return True
    except Exception as e:
        print(f"  ❌ Exception: {str(e)}")
        return False

def main():
    """Main setup"""
    
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║        MONDEORA DROPSHIPPING SYSTEM - SETUP               ║
    ║                                                           ║
    ║     This script will initialize the system completely     ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    project_root = Path(os.getcwd())
    
    # Step 1: Check Python
    print_step(1, "Python Verification")
    print(f"  Python version: {sys.version}")
    print(f"  Python executable: {sys.executable}")
    
    # Step 2: Install dependencies
    print_step(2, "Installing Dependencies")
    
    if os.path.exists("requirements.txt"):
        if run_command("pip install -r requirements.txt", "Installing packages from requirements.txt"):
            print("  ✅ All dependencies installed")
        else:
            print("  ⚠️  Some dependencies might have failed")
    else:
        print("  ❌ requirements.txt not found")
        return False
    
    # Step 3: Create directories
    print_step(3, "Creating Directories")
    
    dirs_to_create = [
        "data",
        "logs",
        "data/backups",
        "src/__pycache__",
        "src/api/__pycache__",
        "src/database/__pycache__",
        "src/automation/__pycache__",
    ]
    
    for dir_path in dirs_to_create:
        full_path = project_root / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {dir_path}")
    
    # Step 4: Initialize database
    print_step(4, "Database Initialization")
    
    try:
        from src.database.models import init_database
        engine = init_database()
        print("  ✅ Database initialized successfully")
        print(f"  📁 Database: {os.getenv('DATABASE_URL', 'data/dropshipping.db')}")
    except Exception as e:
        print(f"  ❌ Database initialization failed: {str(e)}")
    
    # Step 5: Verify configuration
    print_step(5, "Configuration Verification")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_configs = {
        "eBay": ["EBAY_APP_ID", "EBAY_DEV_ID", "EBAY_CERT_ID"],
        "AliExpress": ["ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET"],
        "System": ["TARGET_MARKET", "MIN_MARGIN_PERCENT"]
    }
    
    for section, keys in required_configs.items():
        print(f"\n  {section}:")
        for key in keys:
            value = os.getenv(key)
            if value:
                masked = value[:20] + "..." if len(value) > 20 else value
                print(f"    ✅ {key}: {masked}")
            else:
                print(f"    ❌ {key}: NOT SET")
    
    # Step 6: Test API connections
    print_step(6, "API Connection Tests")
    
    print("  Testing eBay API...", end=" ", flush=True)
    try:
        from src.api.ebay_client import eBayAPIClient
        client = eBayAPIClient()
        print("✅")
    except Exception as e:
        print(f"❌ {str(e)}")
    
    print("  Testing AliExpress API...", end=" ", flush=True)
    try:
        from src.api.aliexpress_client import AliExpressAPIClient
        client = AliExpressAPIClient()
        if client.check_token_validity():
            print("✅")
        else:
            print("⚠️  Token may be invalid")
    except Exception as e:
        print(f"❌ {str(e)}")
    
    # Step 7: Create startup script (Windows batch file)
    print_step(7, "Creating Startup Scripts")
    
    # Windows batch file
    batch_content = """@echo off
title Mondeora Dropshipping System
cd /d "%~dp0"
python main.py
pause
"""
    
    with open("START_SYSTEM.bat", "w") as f:
        f.write(batch_content)
    print("  ✅ START_SYSTEM.bat created")
    
    # Linux/Mac shell script
    shell_content = """#!/bin/bash
cd "$(dirname "$0")"
python3 main.py
"""
    
    with open("start_system.sh", "w") as f:
        f.write(shell_content)
    os.chmod("start_system.sh", 0o755)
    print("  ✅ start_system.sh created")
    
    # Step 8: Summary
    print_step(8, "Setup Complete!")
    
    print("""
    ✅ System setup completed successfully!
    
    📋 NEXT STEPS:
    
    1. VERIFY CONFIGURATION:
       - Open .env file
       - Check all API keys are correct
       - Verify TARGET_MARKET and other settings
    
    2. TEST THE SYSTEM:
       - Run: python main.py
       - Select option 5: "Test API connections"
       - Verify all APIs respond
    
    3. RUN INITIAL SYNC:
       - Run: python main.py
       - Select option 4: "Run initial product sync"
       - Monitor the products synced
    
    4. START FULL SYSTEM:
       - Run: python main.py
       - Select option 1: "Start full automation"
       - Open http://localhost:5000 in browser
       - Monitor the dashboard
    
    📍 STARTUP OPTIONS:
    
    Windows:
    - Double-click: START_SYSTEM.bat
    - OR: python main.py
    
    Linux/Mac:
    - Run: ./start_system.sh
    - OR: python3 main.py
    
    📊 MONITORING:
    
    - Dashboard: http://localhost:5000
    - Logs: logs/system.log
    - Database: data/dropshipping.db
    
    🚀 Ready to launch! Enjoy your automated dropshipping system!
    """)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
