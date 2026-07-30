#!/usr/bin/env python3
"""
CLI test harness for triage service
Allows testing triage from command line
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph.workflow import build_graph
from src.config import settings
from src.utils.logging import setup_logging, logger


async def test_triage(report: str):
    """
    Test triage workflow with a bug report
    
    Args:
        report: Bug report text
    """
    setup_logging()
    
    logger.info("test_triage_start", report_length=len(report))
    
    # TODO: Initialize checkpointer and compile graph
    # For now, just log
    
    print(f"\n{'='*60}")
    print("Bug Report Triage Test")
    print(f"{'='*60}\n")
    print(f"Input: {report[:100]}...")
    print("\n⚠️  Workflow not yet implemented")
    print("\nNext steps:")
    print("1. Implement graph nodes (preprocess, risk_check, etc.)")
    print("2. Wire up LangGraph workflow")
    print("3. Connect to LLM services")
    print(f"\n{'='*60}\n")


def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_triage.py 'bug report text'")
        print("\nExample:")
        print('  python scripts/test_triage.py "Login button not working"')
        sys.exit(1)
    
    report = sys.argv[1]
    asyncio.run(test_triage(report))


if __name__ == "__main__":
    main()
