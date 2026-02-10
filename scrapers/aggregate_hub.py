#!/usr/bin/env python3
"""
TNFirefly Governor Race - Hub Summary Aggregator
Reads all JSON data files and produces hub-summary.json with the
key numbers the hub page needs. Runs after all scrapers.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

def run():
    print("Generating hub summary...")
    
    summary = {
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "candidates": {},
        "endorsementCounts": {},
        "finance": {},
        "latestPoll": None,
        "latestNews": [],
        "raceRatings": []
    }
    
    # === ENDORSEMENTS ===
    try:
        with open(DATA_DIR / "endorsements.json") as f:
            edata = json.load(f)
        for key, info in edata.get("candidates", {}).items():
            summary["endorsementCounts"][key] = info.get("count", "0")
    except Exception as e:
        print(f"  Endorsements: {e}")
    
    # === FINANCE ===
    try:
        with open(DATA_DIR / "finance.json") as f:
            fdata = json.load(f)
        for c in fdata.get("candidates", []):
            name_key = c["name"].split()[-1].lower()  # "Blackburn", "Rose", etc.
            summary["finance"][name_key] = {
                "warChest": c.get("totalRaised", 0) + c.get("personalLoans", 0),
                "totalRaised": c.get("totalRaised", 0),
                "totalSpent": c.get("totalSpent", 0),
                "cashOnHand": c.get("cashOnHand", 0),
                "personalLoans": c.get("personalLoans", 0),
                "contributionCount": c.get("contributionCount", 0),
                "inStatePct": c.get("inStatePct", 0),
                "outStatePct": c.get("outStatePct", 0),
            }
    except Exception as e:
        print(f"  Finance: {e}")
    
    # === POLLS ===
    try:
        with open(DATA_DIR / "polls.json") as f:
            pdata = json.load(f)
        polls = pdata.get("polls", [])
        if polls:
            summary["latestPoll"] = polls[0]
        summary["raceRatings"] = pdata.get("raceRatings", [])
    except Exception as e:
        print(f"  Polls: {e}")
    
    # === NEWS (latest 3) ===
    try:
        with open(DATA_DIR / "news.json") as f:
            ndata = json.load(f)
        articles = ndata.get("articles", [])
        summary["latestNews"] = [
            {"title": a["title"], "source": a["source"], "date": a["date"], "party": a["party"]}
            for a in articles[:3]
        ]
    except Exception as e:
        print(f"  News: {e}")
    
    # === CANDIDATE COUNT ===
    try:
        with open(DATA_DIR / "watchlist.json") as f:
            wdata = json.load(f)
        watching = len(wdata.get("watching", []))
        declined = len(wdata.get("declined", []))
        summary["watchlistCounts"] = {"watching": watching, "declined": declined}
    except Exception as e:
        print(f"  Watchlist: {e}")
    
    # Write
    out = DATA_DIR / "hub-summary.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Saved to: {out}")


if __name__ == "__main__":
    run()
