#!/usr/bin/env python3
"""
TNFirefly Governor Race - News Scraper v2
Sources: National RSS (Fox, AP, Reuters, The Hill), Campaign websites,
         Candidate X feeds via RSSHub bridge.

Filters for TN governor race relevance, auto-detects candidate/party/tags,
and merges with existing news.json.
"""

import json
import re
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import feedparser
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "feedparser"])
    import feedparser

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "requests"])
    import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "beautifulsoup4"])
    from bs4 import BeautifulSoup

from config import (
    NEWS_RSS_FEEDS, CANDIDATE_X_FEEDS, CAMPAIGN_WEBSITES,
    RSSHUB_INSTANCES, GOVERNOR_KEYWORDS,
    CANDIDATE_PATTERNS, TAG_KEYWORDS
)

DATA_DIR = Path(__file__).parent.parent / "data"
NEWS_FILE = DATA_DIR / "news.json"

HEADERS = {
    "User-Agent": "TNFirefly-NewsBot/2.0 (Tennessee education journalism)"
}

# Looser keywords for TNFirefly's own content (no TN signal required)
TNFIREFLY_KEYWORDS = [
    "governor", "gubernatorial", "governor's race",
    "blackburn", "marsha blackburn",
    "john rose", "rose",
    "monty fritts", "fritts",
    "jerri green", "green",
    "carnita atwater", "atwater",
    "adam kurtz", "kurtz",
    "cito pellegra", "pellegra",
    "primary", "candidate", "election",
    "campaign", "endorsement", "polling", "poll",
    "legislature", "legislative session",
    "voucher", "school choice", "education funding",
    "teacher pay", "school funding",
]


# =============================================================
# UTILITY FUNCTIONS
# =============================================================

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
    """Check if article is about the TN governor's race."""
    combined = f"{title} {summary}".lower()
    # Must match at least one keyword
    if not any(kw.lower() in combined for kw in GOVERNOR_KEYWORDS):
        return False
    # Must have some TN connection (skip generic national articles)
    tn_signals = [
        "tennessee", "volunteer state", "nashville", "memphis",
        "blackburn", "rose", "fritts", "green", "atwater", "kurtz",
        "pellegra", "tn gov", "tn governor"
    ]
    return any(sig in combined for sig in tn_signals)


def detect_candidate(title, summary):
    """Detect which candidate an article is about."""
    combined = f"{title} {summary}".lower()
    for pattern, info in CANDIDATE_PATTERNS.items():
        if pattern.lower() in combined:
            return info["party"], info["candidate"]
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
            except Exception:
                pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# =============================================================
# SCRAPER: RSS FEEDS (National sources)
# =============================================================

def scrape_rss_feeds():
    """Scrape national RSS feeds, filter for TN governor race."""
    articles = []
    for feed_config in NEWS_RSS_FEEDS:
        is_tnf = feed_config.get("tier") == "tnfirefly"
        print(f"  RSS: {feed_config['name']}{'  (TNFirefly — loose filter)' if is_tnf else ''}...")
        try:
            feed = feedparser.parse(feed_config["url"])
            count = 0
            for entry in feed.entries[:50]:  # Cap at 50 per feed
                title = strip_html(entry.get("title", ""))
                summary = strip_html(
                    entry.get("summary", "") or
                    entry.get("description", "")
                )

                # TNFirefly uses looser keyword match (no TN signal needed)
                if is_tnf:
                    combined = f"{title} {summary}".lower()
                    if not any(kw in combined for kw in TNFIREFLY_KEYWORDS):
                        continue
                else:
                    if not matches_governor_race(title, summary):
                        continue

                date = parse_date(entry)
                party, candidate = detect_candidate(title, summary)
                tags = detect_tags(title, summary)
                url = entry.get("link", "")

                articles.append({
                    "id": generate_id(title, date),
                    "date": date,
                    "title": title,
                    "summary": summary[:300] + ("..." if len(summary) > 300 else ""),
                    "source": feed_config["source_key"],
                    "url": url,
                    "party": party,
                    "candidate": candidate,
                    "tags": tags,
                    "tnfirefly": is_tnf,
                    "featured": False
                })
                count += 1
            print(f"    Found {count} relevant articles")
        except Exception as e:
            print(f"    ERROR: {e}")
    return articles


# =============================================================
# SCRAPER: CANDIDATE X FEEDS (via RSSHub bridge)
# =============================================================

def scrape_x_feeds():
    """Scrape candidate X/Twitter feeds via RSSHub RSS bridge."""
    articles = []
    for candidate in CANDIDATE_X_FEEDS:
        print(f"  X Feed: @{candidate['handle']}...")
        scraped = False
        for instance in RSSHUB_INSTANCES:
            if scraped:
                break
            rss_url = f"{instance}/twitter/user/{candidate['handle']}"
            try:
                feed = feedparser.parse(rss_url)
                if not feed.entries:
                    continue
                count = 0
                for entry in feed.entries[:20]:
                    title_raw = strip_html(entry.get("title", ""))
                    # X posts are short — use as both title and summary
                    # Truncate title to first sentence or 100 chars
                    title = title_raw[:100].rsplit(" ", 1)[0] + "..." if len(title_raw) > 100 else title_raw
                    summary = title_raw[:300] + ("..." if len(title_raw) > 300 else "")
                    date = parse_date(entry)
                    url = entry.get("link", "")
                    tags = detect_tags(title_raw, "")
                    if "campaign" not in tags:
                        tags.append("campaign")

                    articles.append({
                        "id": generate_id(title_raw, date),
                        "date": date,
                        "title": title,
                        "summary": summary,
                        "source": candidate["source_key"],
                        "url": url,
                        "party": candidate["party"],
                        "candidate": candidate["candidate"],
                        "tags": tags,
                        "tnfirefly": False,
                        "featured": False
                    })
                    count += 1
                print(f"    Found {count} posts via {instance}")
                scraped = True
            except Exception as e:
                print(f"    {instance} failed: {e}")
        if not scraped:
            print(f"    WARNING: All RSSHub instances failed for @{candidate['handle']}")
    return articles


# =============================================================
# SCRAPER: CAMPAIGN WEBSITES (press/news pages)
# =============================================================

def scrape_campaign_sites():
    """Scrape campaign website news/press pages for updates."""
    articles = []
    for site in CAMPAIGN_WEBSITES:
        print(f"  Campaign: {site['name']}...")
        try:
            resp = requests.get(site["url"], headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Try common patterns for news/press pages
            # Pattern 1: article/post elements with links
            post_selectors = [
                "article", ".post", ".news-item", ".press-release",
                ".entry", ".blog-post", ".post-item"
            ]
            posts = []
            for sel in post_selectors:
                posts = soup.select(sel)
                if posts:
                    break

            if not posts:
                # Fallback: find all links that look like news
                posts = soup.find_all("a", href=True)
                posts = [p for p in posts if any(
                    kw in (p.get_text() or "").lower()
                    for kw in ["press", "news", "release", "announce",
                               "campaign", "statement", "report"]
                )]

            count = 0
            for post in posts[:15]:
                # Extract title
                title_el = post.find(["h1", "h2", "h3", "h4", "a"])
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or len(title) < 10:
                    continue

                # Extract link
                link = None
                if title_el.name == "a":
                    link = title_el.get("href", "")
                else:
                    link_el = post.find("a", href=True)
                    link = link_el.get("href", "") if link_el else ""
                if link and not link.startswith("http"):
                    base = site["url"].rstrip("/")
                    link = f"{base}/{link.lstrip('/')}"

                # Extract summary/excerpt
                summary_el = post.find(["p", ".excerpt", ".summary"])
                summary = summary_el.get_text(strip=True) if summary_el else ""
                summary = summary[:300] + ("..." if len(summary) > 300 else "")

                # Try to find a date
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                time_el = post.find("time")
                if time_el and time_el.get("datetime"):
                    try:
                        date_str = time_el["datetime"][:10]
                    except Exception:
                        pass

                tags = detect_tags(title, summary)
                if "campaign" not in tags:
                    tags.append("campaign")

                articles.append({
                    "id": generate_id(title, date_str),
                    "date": date_str,
                    "title": title,
                    "summary": summary,
                    "source": site["source_key"],
                    "url": link or "",
                    "party": site["party"],
                    "candidate": site["candidate"],
                    "tags": tags,
                    "tnfirefly": False,
                    "featured": False
                })
                count += 1
            print(f"    Found {count} press items")
        except Exception as e:
            print(f"    ERROR: {e}")
    return articles


# =============================================================
# MERGE & OUTPUT
# =============================================================

def merge_articles(existing, new_articles):
    """Merge new articles with existing, deduplicating by ID."""
    existing_ids = {a["id"] for a in existing}
    added = 0
    for article in new_articles:
        if article["id"] not in existing_ids:
            existing.append(article)
            existing_ids.add(article["id"])
            added += 1
            print(f"    + NEW: {article['source']}: {article['title'][:60]}...")
    # Sort by date descending
    existing.sort(key=lambda a: a["date"], reverse=True)
    return existing, added


def run():
    """Main entry point."""
    print("=" * 60)
    print("TNFirefly Governor Race - News Scraper v2")
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

    # --- Scrape all sources ---
    all_new = []

    # 1. National RSS feeds
    print("\n--- National RSS Feeds ---")
    rss_articles = scrape_rss_feeds()
    all_new.extend(rss_articles)

    # 2. Candidate X feeds
    print("\n--- Candidate X Feeds ---")
    x_articles = scrape_x_feeds()
    all_new.extend(x_articles)

    # 3. Campaign websites
    print("\n--- Campaign Websites ---")
    campaign_articles = scrape_campaign_sites()
    all_new.extend(campaign_articles)

    print(f"\nTotal scraped: {len(all_new)} articles")
    print(f"  RSS: {len(rss_articles)}")
    print(f"  X feeds: {len(x_articles)}")
    print(f"  Campaign sites: {len(campaign_articles)}")

    # Merge
    print("\nMerging with existing data...")
    merged, added = merge_articles(existing, all_new)

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
