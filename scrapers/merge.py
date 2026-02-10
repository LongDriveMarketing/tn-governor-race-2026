#!/usr/bin/env python3
"""
TNFirefly Governor Race - Data Merge
====================================
Combines scraped data with manual.json to produce final output files.
Manual entries ALWAYS win on conflicts.

Flow: scraped/*.json + manual.json → data/*.json (final output)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
SCRAPED_DIR = DATA_DIR / "scraped"
MANUAL_FILE = DATA_DIR / "manual.json"


def load_json(path):
    """Load a JSON file, return empty dict if missing."""
    if path.exists():
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            return json.load(f)
    return {}


def save_json(path, data):
    """Write JSON with pretty formatting."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─── Merge Helpers ────────────────────────────────────────────

def merge_by_id(existing, additions, id_key="id"):
    """Merge two lists by ID. Additions win on conflict."""
    by_id = {item[id_key]: item for item in existing if id_key in item}
    for item in additions:
        by_id[item[id_key]] = item  # manual wins
    return list(by_id.values())


def merge_by_name(existing, additions, name_key="name"):
    """Merge two lists by name. Additions are appended if not present."""
    existing_names = {item[name_key].lower() for item in existing}
    merged = list(existing)
    for item in additions:
        if item[name_key].lower() not in existing_names:
            merged.append(item)
            existing_names.add(item[name_key].lower())
    return merged


def merge_grouped_data(scraped_groups, manual_groups):
    """Merge grouped dicts like issuePolling: {topic: [entries]}.
    Manual entries are added to matching topics, new topics created."""
    merged = {}
    # Start with all scraped groups
    for key, items in scraped_groups.items():
        merged[key] = list(items)
    # Add manual entries
    for key, items in manual_groups.items():
        if key not in merged:
            merged[key] = []
        # Deduplicate by source+poll combo
        existing_keys = {
            f"{e.get('source','')}-{e.get('poll','')}" for e in merged[key]
        }
        for item in items:
            item_key = f"{item.get('source','')}-{item.get('poll','')}"
            if item_key not in existing_keys:
                merged[key].append(item)
                existing_keys.add(item_key)
    return merged


# ─── Polls Merge ──────────────────────────────────────────────

def merge_polls():
    """Merge scraped polls with manual poll data."""
    scraped = load_json(SCRAPED_DIR / "polls.json")
    manual = load_json(MANUAL_FILE).get("polls", {})

    if not scraped:
        print("  [WARN] No scraped polls found — using manual only")
        scraped = {
            "pollingSources": [], "raceRatings": [], "polls": [],
            "generalPolls": [], "trendline": {"description": "", "data": []},
            "approvalRatings": {}, "issuePolling": {},
            "politicalEnvironment": {}, "aggregators": {}, "analysis": ""
        }

    # 1. Merge polling sources (manual sources added if not already present)
    scraped_sources = scraped.get("pollingSources", [])
    manual_sources = manual.get("sources", [])
    scraped["pollingSources"] = merge_by_name(scraped_sources, manual_sources)

    # 2. Merge poll entries (manual wins on ID conflict)
    scraped_polls = scraped.get("polls", [])
    manual_polls = manual.get("polls", [])
    scraped["polls"] = merge_by_id(scraped_polls, manual_polls)
    scraped["polls"].sort(key=lambda p: p.get("date", "0000"), reverse=True)

    # 3. Merge issue polling (add manual topics/entries)
    scraped_issues = scraped.get("issuePolling", {})
    manual_issues = manual.get("issuePolling", {})
    scraped["issuePolling"] = merge_grouped_data(scraped_issues, manual_issues)

    # 4. Merge trendline (add manual data points, override description)
    scraped_trend = scraped.get("trendline", {"description": "", "data": []})
    manual_trend = manual.get("trendline", {})

    if manual_trend.get("data"):
        # Add manual trendline data points (by date+pollster)
        existing_keys = {
            f"{d.get('date','')}-{d.get('pollster','')}"
            for d in scraped_trend.get("data", [])
        }
        for point in manual_trend["data"]:
            key = f"{point.get('date','')}-{point.get('pollster','')}"
            if key not in existing_keys:
                scraped_trend["data"].append(point)
        scraped_trend["data"].sort(key=lambda d: d.get("date", "0000"))

    if manual_trend.get("description"):
        scraped_trend["description"] = manual_trend["description"]

    scraped["trendline"] = scraped_trend

    # 5. Override analysis if manual provides one
    if manual.get("analysis"):
        scraped["analysis"] = manual["analysis"]

    # 6. Update timestamp
    scraped["lastUpdated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    scraped["lastMerged"] = datetime.now(timezone.utc).isoformat()

    # Save final output
    save_json(DATA_DIR / "polls.json", scraped)
    n_manual_polls = len(manual_polls)
    n_manual_issues = sum(len(v) for v in manual_issues.values())
    print(f"  polls.json: {len(scraped['polls'])} polls ({n_manual_polls} manual), "
          f"{len(scraped['issuePolling'])} issue topics ({n_manual_issues} manual entries)")


# ─── News Merge ───────────────────────────────────────────────

def merge_news():
    """Merge scraped news with manual news articles."""
    scraped = load_json(SCRAPED_DIR / "news.json")
    manual = load_json(MANUAL_FILE).get("news", {})

    if not scraped:
        print("  [WARN] No scraped news found — using manual only")
        scraped = {"articles": []}

    scraped_articles = scraped.get("articles", [])
    manual_articles = manual.get("articles", [])

    # Manual articles win on ID conflict
    merged = merge_by_id(scraped_articles, manual_articles)
    merged.sort(key=lambda a: a.get("date", "0000"), reverse=True)

    output = {
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "lastMerged": datetime.now(timezone.utc).isoformat(),
        "articles": merged
    }
    save_json(DATA_DIR / "news.json", output)
    print(f"  news.json: {len(merged)} articles ({len(manual_articles)} manual)")


# ─── Endorsements (pass-through, no manual layer needed yet) ─

def merge_endorsements():
    """Copy scraped endorsements to final output (no manual overrides yet)."""
    scraped = load_json(SCRAPED_DIR / "endorsements.json")
    if scraped:
        save_json(DATA_DIR / "endorsements.json", scraped)
        count = len(scraped.get("endorsements", []))
        print(f"  endorsements.json: {count} endorsements (scraped only)")
    else:
        print("  [WARN] No scraped endorsements found — skipping")


# ─── Main ─────────────────────────────────────────────────────

def run():
    """Merge all data sources into final output files."""
    print("=" * 60)
    print("TNFirefly Governor Race - Data Merge")
    print(f"Run time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # Ensure scraped directory exists
    SCRAPED_DIR.mkdir(exist_ok=True)

    # Check manual file
    if MANUAL_FILE.exists():
        manual = load_json(MANUAL_FILE)
        manual_sections = [k for k in manual if not k.startswith("_")]
        print(f"  Manual overrides: {', '.join(manual_sections)}")
    else:
        print("  No manual.json found — scraped data only")

    # Merge each data type
    print("\nMerging polls...")
    merge_polls()

    print("\nMerging news...")
    merge_news()

    print("\nMerging endorsements...")
    merge_endorsements()

    print("\n" + "=" * 60)
    print("  Merge complete. Final output in data/")
    print("=" * 60)


if __name__ == "__main__":
    run()
