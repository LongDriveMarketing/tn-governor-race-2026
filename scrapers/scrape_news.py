#!/usr/bin/env python3
"""
TNFirefly Governor Race - News Scraper
Scrapes RSS feeds from TN news outlets, filters for governor race content,
auto-detects candidate/party/tags, and merges with existing news.json.

Run manually or via GitHub Actions on a schedule.
"""

import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path

try:
    import feedparser
except ImportError:
    print("Installing feedparser...")
    import subprocess
    subprocess.check_call(["pip", "install", "feedparser"])
    import feedparser

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing beautifulsoup4...")
    import subprocess
    subprocess.check_call(["pip", "install", "beautifulsoup4"])
    from bs4 import BeautifulSoup

from config import (
    NEWS_RSS_FEEDS, GOVERNOR_KEYWORDS,
    CANDIDATE_PATTERNS, TAG_KEYWORDS
)

DATA_DIR = Path(__file__).parent.parent / "data"
NEWS_FILE = DATA_DIR / "news.json"


def generate_id(title, date):
    """Generate stable unique ID from title + date."""
    raw = f"{title}-{date}".lower()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def strip_html(text):
    """Remove HTML tags from text."""
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(separator=" ").strip()


def matches_governor_race(title, summary):
    """Check if article is about the governor's race."""
    combined = f"{title} {summary}".lower()
    return any(kw.lower() in combined for kw in GOVERNOR_KEYWORDS)


def detect_candidate(title, summary):
    """Detect which candidate an article is about."""
    combined = f"{title} {summary}".lower()
    for pattern, info in CANDIDATE_PATTERNS.items():
        if pattern.lower() in combined:
            return info["party"], info["candidate"]
    # No specific candidate detected
    return "general", ""


def detect_tags(title, summary):
    """Auto-detect tags based on content keywords."""
    combined = f"{title} {summary}".lower()
    tags = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            tags.append(tag)
    return tags if tags else ["campaign"]


def parse_date(entry):
    """Extract and normalize date from feed entry."""
    for field in ["published_parsed", "updated_parsed"]:
        parsed = getattr(entry, field, None)
        if parsed:
            try:
                return datetime(*parsed[:6]).strftime("%Y-%m-%d")
            except:
                pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def scrape_feeds():
    """Scrape all RSS feeds and return governor-race articles."""
    new_articles = []
    
    for feed_config in NEWS_RSS_FEEDS:
        print(f"  Scraping: {feed_config['name']}...")
        try:
            feed = feedparser.parse(feed_config["url"])
            count = 0
            for entry in feed.entries:
                title = strip_html(entry.get("title", ""))
                summary = strip_html(
                    entry.get("summary", "") or 
                    entry.get("description", "")
                )
                
                if not matches_governor_race(title, summary):
                    continue
                
                date = parse_date(entry)
                party, candidate = detect_candidate(title, summary)
                tags = detect_tags(title, summary)
                url = entry.get("link", "")
                
                article = {
                    "id": generate_id(title, date),
                    "date": date,
                    "title": title,
                    "summary": summary[:300] + ("..." if len(summary) > 300 else ""),
                    "source": feed_config["source_key"],
                    "url": url,
                    "party": party,
                    "candidate": candidate,
                    "tags": tags,
                    "tnfirefly": False,
                    "featured": False
                }
                new_articles.append(article)
                count += 1
            
            print(f"    Found {count} governor race articles")
        except Exception as e:
            print(f"    ERROR scraping {feed_config['name']}: {e}")
    
    return new_articles


def merge_articles(existing, new_articles):
    """Merge new articles with existing, deduplicating by ID."""
    existing_ids = {a["id"] for a in existing}
    added = 0
    
    for article in new_articles:
        if article["id"] not in existing_ids:
            existing.append(article)
            existing_ids.add(article["id"])
            added += 1
            print(f"    + NEW: {article['title'][:60]}...")
    
    # Sort by date descending
    existing.sort(key=lambda a: a["date"], reverse=True)
    return existing, added


def run():
    """Main entry point."""
    print("=" * 60)
    print("TNFirefly Governor Race - News Scraper")
    print(f"Run time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    
    # Load existing
    if NEWS_FILE.exists():
        with open(NEWS_FILE, "r") as f:
            data = json.load(f)
        existing = data.get("articles", [])
        print(f"Loaded {len(existing)} existing articles")
    else:
        existing = []
        print("No existing news.json found, starting fresh")
    
    # Scrape
    print("\nScraping RSS feeds...")
    new_articles = scrape_feeds()
    print(f"\nFound {len(new_articles)} governor race articles total")
    
    # Merge
    print("\nMerging with existing data...")
    merged, added = merge_articles(existing, new_articles)
    
    # Save
    output = {
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "lastScraped": datetime.now(timezone.utc).isoformat(),
        "articles": merged
    }
    
    with open(NEWS_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nDone! {added} new articles added. Total: {len(merged)}")
    print(f"Saved to: {NEWS_FILE}")
    return added


if __name__ == "__main__":
    run()
