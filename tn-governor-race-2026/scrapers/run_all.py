#!/usr/bin/env python3
"""
TNFirefly Governor Race - Master Scraper
Runs all scrapers in sequence and reports results.
Designed to be called by GitHub Actions on a cron schedule.
"""

import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# Add scrapers dir to path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    print("=" * 70)
    print("  TNFirefly Governor Race Tracker - Automated Data Update")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)
    
    results = {}
    
    # 1. News scraper
    print("\n[1/2] RUNNING NEWS SCRAPER...")
    print("-" * 40)
    try:
        from scrape_news import run as run_news
        added = run_news()
        results["news"] = f"OK - {added} new articles"
    except Exception as e:
        results["news"] = f"FAILED - {e}"
        print(f"NEWS SCRAPER ERROR: {e}")
    
    # 2. Polls & candidates scraper
    print("\n[2/2] RUNNING POLLS & CANDIDATES SCRAPER...")
    print("-" * 40)
    try:
        from scrape_polls import run as run_polls
        run_polls()
        results["polls"] = "OK"
    except Exception as e:
        results["polls"] = f"FAILED - {e}"
        print(f"POLLS SCRAPER ERROR: {e}")
    
    # 3. Hub aggregator
    print("\n[3/3] AGGREGATING HUB SUMMARY...")
    print("-" * 40)
    try:
        from aggregate_hub import run as run_hub
        run_hub()
        results["hub"] = "OK"
    except Exception as e:
        results["hub"] = f"FAILED - {e}"
        print(f"HUB AGGREGATOR ERROR: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    for scraper, status in results.items():
        icon = "✓" if "OK" in status else "✗"
        print(f"  {icon} {scraper}: {status}")
    print("=" * 70)
    
    # Exit with error if any scraper failed
    if any("FAILED" in s for s in results.values()):
        sys.exit(1)

if __name__ == "__main__":
    main()
