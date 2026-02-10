#!/usr/bin/env python3
"""
TNFirefly Governor Race - Facebook Scraper (Apify)
Scrapes public Facebook page posts via Apify's managed scraper.
No login required, handles anti-bot, proxy rotation automatically.

Requires: APIFY_TOKEN environment variable (free tier: 48 runs/month)
Sign up: https://console.apify.com/sign-up
"""

import json
import hashlib
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from apify_client import ApifyClient
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "apify-client"])
    from apify_client import ApifyClient

from config import TAG_KEYWORDS

DATA_DIR = Path(__file__).parent.parent / "data"
SCRAPED_DIR = DATA_DIR / "scraped"
SCRAPED_DIR.mkdir(exist_ok=True)
NEWS_FILE = SCRAPED_DIR / "news.json"

# =============================================================
# FACEBOOK PAGES TO SCRAPE
# =============================================================

FACEBOOK_PAGES = [
    {
        "page_url": "https://www.facebook.com/votemarshablackburn",
        "source_key": "Blackburn (Facebook)",
        "candidate": "Blackburn",
        "party": "rep"
    },
    {
        "page_url": "https://www.facebook.com/JohnRoseforTN",
        "source_key": "Rose (Facebook)",
        "candidate": "Rose",
        "party": "rep"
    },
    {
        "page_url": "https://www.facebook.com/profile.php?id=61580207799026",
        "source_key": "Fritts (Facebook)",
        "candidate": "Fritts",
        "party": "rep"
    },
]

# Apify actor ID for the official Facebook Posts Scraper
APIFY_ACTOR = "apify/facebook-posts-scraper"

# How many posts to grab per page
RESULTS_LIMIT = 15

# Only keep posts from the last N days
MAX_AGE_DAYS = 90


# =============================================================
# UTILITIES
# =============================================================

def generate_id(text, date):
    """Stable unique ID from post text + date."""
    raw = f"fb-{text[:100]}-{date}".lower()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def detect_tags(text):
    """Auto-detect tags from post text."""
    lower = text.lower()
    tags = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            tags.append(tag)
    return tags if tags else ["campaign"]


def is_relevant(text):
    """Filter out generic holiday/constituent posts."""
    if not text or len(text.strip()) < 20:
        return False
    lower = text.lower()
    skip_signals = [
        "happy birthday", "merry christmas", "happy thanksgiving",
        "happy easter", "rest in peace", "condolences",
        "office hours this week", "flag day"
    ]
    return not any(sig in lower for sig in skip_signals)


def truncate_title(text, max_len=120):
    """Create a title from the first sentence or first N chars."""
    # Try first sentence
    for sep in [". ", "! ", "? ", "\n"]:
        idx = text.find(sep)
        if 20 < idx < max_len:
            return text[:idx + 1].strip()
    # Fall back to truncation
    if len(text) > max_len:
        return text[:max_len].rsplit(" ", 1)[0] + "..."
    return text.strip()


# =============================================================
# SCRAPER
# =============================================================

def scrape_facebook_posts():
    """Scrape Facebook pages via Apify and return article dicts."""
    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        print("  WARNING: APIFY_TOKEN not set. Skipping Facebook scraper.")
        print("  Set it as a GitHub Actions secret or env variable.")
        print("  Sign up free: https://console.apify.com/sign-up")
        return []

    client = ApifyClient(token)
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    articles = []

    for page in FACEBOOK_PAGES:
        print(f"  Facebook: {page['source_key']}...")
        try:
            run_input = {
                "startUrls": [{"url": page["page_url"]}],
                "resultsLimit": RESULTS_LIMIT,
            }

            # Run the Actor and wait for completion
            run = client.actor(APIFY_ACTOR).call(run_input=run_input)

            # Fetch results from the dataset
            dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
            count = 0

            for item in dataset_items:
                # Extract post text
                text = item.get("text", "") or item.get("message", "") or ""
                if not text:
                    continue
                if not is_relevant(text):
                    continue

                # Parse date
                post_time = item.get("time")
                if post_time:
                    try:
                        if isinstance(post_time, str):
                            dt = datetime.fromisoformat(post_time.replace("Z", "+00:00"))
                        else:
                            dt = datetime.fromtimestamp(post_time, tz=timezone.utc)
                        if dt < cutoff:
                            continue
                        date_str = dt.strftime("%Y-%m-%d")
                    except Exception:
                        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                else:
                    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                # Build article
                title = truncate_title(text)
                summary = text[:300] + ("..." if len(text) > 300 else "")
                post_url = item.get("url", "") or item.get("postUrl", "") or ""
                tags = detect_tags(text)
                if "campaign" not in tags:
                    tags.append("campaign")

                articles.append({
                    "id": generate_id(text, date_str),
                    "date": date_str,
                    "title": title,
                    "summary": summary,
                    "source": page["source_key"],
                    "url": post_url,
                    "party": page["party"],
                    "candidate": page["candidate"],
                    "tags": tags,
                    "tnfirefly": False,
                    "featured": False
                })
                count += 1

            print(f"    Fetched {len(dataset_items)} posts, {count} relevant")

        except Exception as e:
            print(f"    ERROR: {e}")

    return articles


# =============================================================
# MERGE & RUN
# =============================================================

def run():
    """Main entry point — called by run_all.py or standalone."""
    print("=" * 60)
    print("TNFirefly Governor Race - Facebook Scraper (Apify)")
    print(f"Run time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # Load existing news (scraped version, or fall back to main data/)
    if NEWS_FILE.exists():
        with open(NEWS_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        existing = data.get("articles", [])
    elif (DATA_DIR / "news.json").exists():
        with open(DATA_DIR / "news.json", "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        existing = data.get("articles", [])
    else:
        existing = []
    print(f"Loaded {len(existing)} existing articles")

    # Scrape
    new_articles = scrape_facebook_posts()
    print(f"\nScraped {len(new_articles)} relevant FB posts")

    # Merge (deduplicate by ID)
    existing_ids = {a["id"] for a in existing}
    added = 0
    for article in new_articles:
        if article["id"] not in existing_ids:
            existing.append(article)
            existing_ids.add(article["id"])
            added += 1
            print(f"  + NEW: {article['title'][:60]}...")

    # Sort by date descending
    existing.sort(key=lambda a: a["date"], reverse=True)

    # Save
    output = {
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "lastScraped": datetime.now(timezone.utc).isoformat(),
        "articles": existing
    }
    with open(NEWS_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone! {added} new FB posts added. Total: {len(existing)}")
    return added


if __name__ == "__main__":
    run()
