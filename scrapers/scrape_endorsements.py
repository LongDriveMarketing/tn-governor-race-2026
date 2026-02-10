#!/usr/bin/env python3
"""
TNFirefly Governor Race - Endorsement Scraper
Scrapes Wikipedia's 2026 TN Governor election endorsements section,
compares against current endorsements.json, and flags new additions.

New endorsements are auto-added with basic info. The editorial team
can then add notes/context manually.

Sources:
  - Wikipedia: 2026 Tennessee gubernatorial election (endorsement tables)
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
SCRAPED_DIR = DATA_DIR / "scraped"
SCRAPED_DIR.mkdir(exist_ok=True)
ENDORSEMENTS_FILE = SCRAPED_DIR / "endorsements.json"
ALERTS_FILE = SCRAPED_DIR / "endorsements-alerts.json"

# Wikipedia URL
WIKI_URL = "https://en.wikipedia.org/wiki/2026_Tennessee_gubernatorial_election"
# Map endorsement box titles to our candidate keys
CANDIDATE_MAP = {
    "marsha blackburn": "blackburn",
    "blackburn": "blackburn",
    "john rose": "rose",
    "rose": "rose",
    "jerri green": "green",
    "green": "green",
    "monty fritts": "fritts",
    "fritts": "fritts",
}


def load_current_endorsements():
    """Load the current endorsements.json. Falls back to main data/ if scraped version doesn't exist."""
    if ENDORSEMENTS_FILE.exists():
        with open(ENDORSEMENTS_FILE, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    # Bootstrap: fall back to main data dir on first run
    fallback = DATA_DIR / "endorsements.json"
    if fallback.exists():
        with open(fallback, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return {"endorsements": [], "holdouts": [], "candidates": {}}


def get_existing_names(data):
    """Extract all endorser names from current data (lowercased for matching)."""
    names = set()
    for e in data.get("endorsements", []):
        names.add(e["name"].lower().strip())
    for h in data.get("holdouts", []):
        names.add(h["name"].lower().strip())
    return names

def scrape_wikipedia_endorsements():
    """
    Scrape Wikipedia endorsement boxes for the 2026 TN Governor race.
    Wikipedia uses: div.endorsements-box > div.endorsements-box-title + 
    div.endorsements-box-list containing dl/dt (categories) and ul/li (endorsers).
    Returns list of dicts: {name, role, candidate, type, source}
    """
    print("  Fetching Wikipedia page...")
    headers = {"User-Agent": "TNFirefly-Bot/1.0 (education journalism)"}
    resp = requests.get(WIKI_URL, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    endorsements = []

    # Find all endorsement boxes
    boxes = soup.find_all("div", class_="endorsements-box")
    print(f"  Found {len(boxes)} endorsement box(es)")

    for box in boxes:
        # Get candidate name from title div
        title_div = box.find("div", class_="endorsements-box-title")
        if not title_div:
            continue
        title_text = title_div.get_text(strip=True).lower()

        # Skip "declined to endorse" box
        if "decline" in title_text:
            continue

        # Map to our candidate key
        candidate_key = None
        for pattern, key in CANDIDATE_MAP.items():
            if pattern in title_text:
                candidate_key = key
                break
        if not candidate_key:
            print(f"  WARNING: Unknown candidate box: {title_text}")
            continue
        # Parse the endorsement list
        list_div = box.find("div", class_="endorsements-box-list")
        if not list_div:
            continue

        current_category = "Unknown"

        # Walk through children: dl/dt = category, ul = endorser list
        for child in list_div.children:
            if not hasattr(child, "name") or not child.name:
                continue

            # dl contains dt which is the category header
            if child.name == "dl":
                dt = child.find("dt")
                if dt:
                    current_category = dt.get_text(strip=True)
                    # Remove citation brackets
                    current_category = re.sub(r"\[\d+\]", "", current_category).strip()

            # ul contains li items = individual endorsers
            elif child.name == "ul":
                for li in child.find_all("li", recursive=False):
                    name, role = _parse_endorser_li(li, current_category)
                    if name and len(name) >= 3:
                        etype = _categorize_type(current_category)
                        endorsements.append({
                            "name": name,
                            "role": role,
                            "candidate": candidate_key,
                            "type": etype,
                            "source": "Wikipedia"
                        })

    print(f"  Found {len(endorsements)} total endorsements on Wikipedia")
    return endorsements

def _parse_endorser_li(li, category):
    """Extract name and role from a Wikipedia list item.
    
    Wikipedia formats endorsers as: 'Name, role/title (years)'
    The name is ALWAYS the text before the first comma. We prefer
    the first <a> link text only if it appears before any comma.
    """
    full_text = li.get_text(strip=True)
    # Remove citation brackets like [1], [2]
    full_text = re.sub(r"\[\d+\]", "", full_text).strip()
    # Normalize whitespace (Wikipedia sometimes collapses spaces)
    full_text = re.sub(r"\s+", " ", full_text).strip()

    # Strategy 1: Use the first <a> link if it looks like a person name
    place_words = ["county", "city", "district", "council", "state", "house",
                   "senate", "tennessee", "memphis", "nashville", "representative",
                   "governor", "mayor", "speaker", "leader"]
    
    first_link = li.find("a")
    if first_link:
        link_text = first_link.get_text(strip=True)
        link_is_place = any(w in link_text.lower() for w in place_words)

        if not link_is_place:
            # First link IS the person name
            name = link_text
            role = full_text.replace(link_text, "", 1).strip().lstrip(",").strip()
            return name, role if role else category

    # Strategy 2: Split on first comma
    parts = full_text.split(",", 1)
    name = parts[0].strip()
    role = parts[1].strip() if len(parts) > 1 else ""

    # If name still looks like a title, try ALL <a> links for a person
    if any(w in name.lower() for w in place_words):
        found_person = False
        for link in li.find_all("a"):
            lt = link.get_text(strip=True)
            if not any(w in lt.lower() for w in place_words) and len(lt) > 3:
                name = lt
                role = full_text.replace(lt, "", 1).strip().lstrip(",").strip()
                found_person = True
                break

        # Strategy 3: Person name might be plain text after a title link
        # e.g. <a>Memphis City Councilwoman</a> Michalyn Easter-Thomas
        if not found_person:
            # Get the title from the first link
            title_link = li.find("a")
            title_text = title_link.get_text(strip=True) if title_link else ""
            for child in li.children:
                if isinstance(child, str):
                    text = child.strip().lstrip(",").strip()
                    if text and len(text) > 3 and not any(w in text.lower() for w in place_words):
                        role = title_text  # use the link text as the role
                        name = text
                        found_person = True
                        break

    return name, role if role else category


def _categorize_type(category):
    """Map Wikipedia category header to our type system."""
    cat = (category or "").lower()
    if any(w in cat for w in ["organization", "pac", "interest"]):
        return "org"
    if any(w in cat for w in ["business", "media", "commentator"]):
        return "notable"
    return "elected"

def _normalize_name(name):
    """Normalize a name for comparison: lowercase, collapse whitespace, strip suffixes."""
    n = name.lower().strip()
    n = re.sub(r"\s+", " ", n)  # collapse whitespace
    # Strip common suffixes for matching
    for suffix in [" pac", " action", " america", " inc", " llc"]:
        n = n.replace(suffix, "")
    return n.strip()


def find_new_endorsements(wiki_endorsements, existing_names):
    """Compare Wikipedia endorsements against our current data.
    Uses fuzzy substring matching to avoid duplicates like
    'Club for Growth' vs 'Club for Growth PAC'.
    """
    normalized_existing = {_normalize_name(n) for n in existing_names}
    new = []
    for e in wiki_endorsements:
        name_lower = e["name"].lower().strip()
        name_norm = _normalize_name(e["name"])
        if any(skip in name_lower for skip in ["edit", "list", "reference"]):
            continue

        # Exact match
        if name_lower in existing_names or name_norm in normalized_existing:
            continue

        # Fuzzy match: substring check on both raw and normalized
        is_duplicate = False
        for existing in existing_names:
            ex_norm = _normalize_name(existing)
            if (name_lower in existing or existing in name_lower or
                name_norm in ex_norm or ex_norm in name_norm):
                is_duplicate = True
                break
        if is_duplicate:
            continue

        new.append(e)
    return new


def auto_add_endorsements(data, new_endorsements):
    """Add new endorsements to data. Only adds, never removes."""
    added = 0
    for e in new_endorsements:
        entry = {
            "candidate": e["candidate"],
            "name": e["name"],
            "role": e["role"],
            "type": e["type"],
            "note": "Auto-detected from Wikipedia. Verify and add context."
        }
        data["endorsements"].append(entry)
        added += 1
        print(f"  + ADDED: {e['name']} -> {e['candidate']} ({e['role'][:60]})")

    if added > 0:
        for cand_key in data["candidates"]:
            count = sum(1 for x in data["endorsements"]
                        if x["candidate"] == cand_key
                        and "State Legislators" not in x.get("name", "")
                        and "Donors" not in x.get("name", ""))
            if cand_key == "blackburn":
                data["candidates"][cand_key]["count"] = f"{count}+"
            else:
                data["candidates"][cand_key]["count"] = str(count)
        data["lastUpdated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return added

def save_alerts(new_endorsements):
    """Save new endorsements to alerts file for editorial review."""
    alert_data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "count": len(new_endorsements),
        "new_endorsements": new_endorsements
    }
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(alert_data, f, indent=2, ensure_ascii=False)
    print(f"  Alerts saved to {ALERTS_FILE.name}")


def run():
    """Main entry point for the endorsement scraper."""
    print("Loading current endorsements...")
    data = load_current_endorsements()
    existing = get_existing_names(data)
    print(f"  Current endorsers tracked: {len(existing)}")

    # Scrape Wikipedia
    print("\nScraping Wikipedia endorsements...")
    wiki = scrape_wikipedia_endorsements()

    # Find new
    new = find_new_endorsements(wiki, existing)

    if not new:
        print("\n  [OK] No new endorsements found. Data is current.")
        return 0

    print(f"\n  [NEW] Found {len(new)} NEW endorsement(s)!")

    # Save alerts file for editorial review
    save_alerts(new)

    # Auto-add to endorsements.json
    added = auto_add_endorsements(data, new)

    # Write updated file
    with open(ENDORSEMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n  [OK] Updated endorsements.json with {added} new entries")
    print("  [!!] Review auto-added entries and add editorial notes.")

    return added


if __name__ == "__main__":
    run()