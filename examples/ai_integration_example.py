"""
Example: Using AI Tools in Mondeora Dropshipping
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from ai_agents.dropshipping_ai_assistant import get_assistant


def main():
    print("\n🚀 MONDEORA AI INTEGRATION EXAMPLES\n")
    
    assistant = get_assistant()
    status = assistant.get_system_status()
    
    print(f"System Status: {status['status']}")
    print(f"AI Tools: {', '.join(status['ai_tools'])}")
    print(f"Agency Agents: {status['agency_agents']}")
    print(f"\n✅ AI Integration ready!\n")


if __name__ == '__main__':
    main()
