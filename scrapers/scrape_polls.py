#!/usr/bin/env python3
"""
TNFirefly Governor Race - Polls & Candidates Scraper
Scrapes polling data from 270toWin and Ballotpedia,
and candidate filing data from TN Secretary of State.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

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

from config import POLLING_URLS, SOS_CANDIDATE_URL, TENNSIGHT_URLS

DATA_DIR = Path(__file__).parent.parent / "data"
POLLS_FILE = DATA_DIR / "polls.json"
CANDIDATES_FILE = DATA_DIR / "candidates.json"

HEADERS = {
    "User-Agent": "TNFirefly-GovernorTracker/1.0 (info@tnfirefly.com)"
}


def scrape_tennsight():
    """Scrape Beacon Center / TennSight elections page for governor race polling."""
    url = TENNSIGHT_URLS["elections"]
    print(f"  Scraping TennSight elections: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        results = []
        
        # Look for governor race data in the page text
        page_text = soup.get_text()
        
        # Pattern: "X% of Tennessee Republican primary voters support Senator Marsha Blackburn"
        import re
        
        # Find governor primary mentions
        gov_pattern = re.compile(
            r'(\d+)%.*?(?:Republican primary|primary for Governor).*?'
            r'(?:Blackburn|Rose|Fritts)',
            re.IGNORECASE | re.DOTALL
        )
        
        # Find poll links to individual poll pages
        poll_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/polls/' in href and any(m in href for m in ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']):
                full_url = href if href.startswith('http') else f"https://tennsight.com{href}"
                if full_url not in poll_links:
                    poll_links.append(full_url)
        
        print(f"    Found {len(poll_links)} poll page links")
        
        # Scrape each poll page for governor data
        for poll_url in poll_links[:4]:  # Last 4 polls max
            try:
                print(f"    Checking: {poll_url}")
                pr = requests.get(poll_url, headers=HEADERS, timeout=15)
                pr.raise_for_status()
                psoup = BeautifulSoup(pr.text, "html.parser")
                ptext = psoup.get_text()
                
                # Check if this poll has governor race data
                if 'governor' in ptext.lower() or 'blackburn' in ptext.lower():
                    # Extract fieldwork dates
                    dates_match = re.search(r'Fieldwork:\s*(\w+ \d+)\s*through\s*(\w+ \d+,\s*\d{4})', ptext)
                    
                    # Extract percentages for candidates
                    blackburn_match = re.search(r'(\d+)%.*?(?:support|for)\s+(?:Senator\s+)?(?:Marsha\s+)?Blackburn', ptext, re.IGNORECASE)
                    rose_match = re.search(r'(?:John\s+)?Rose\s+(?:garnering|at|coming in.*?at)\s+(\d+)%', ptext, re.IGNORECASE)
                    fritts_match = re.search(r'(?:Monty\s+)?Fritts\s+(?:coming in.*?at|at)\s+(\d+)%', ptext, re.IGNORECASE)
                    undecided_match = re.search(r'(\d+)%.*?(?:undecided|remain undecided)', ptext, re.IGNORECASE)
                    
                    if blackburn_match:
                        poll_data = {
                            "url": poll_url,
                            "blackburn": int(blackburn_match.group(1)),
                            "rose": int(rose_match.group(1)) if rose_match else None,
                            "fritts": int(fritts_match.group(1)) if fritts_match else None,
                            "undecided": int(undecided_match.group(1)) if undecided_match else None,
                            "dates": dates_match.group(0) if dates_match else ""
                        }
                        results.append(poll_data)
                        print(f"      → Governor data: Blackburn {poll_data['blackburn']}%, Rose {poll_data.get('rose','?')}%, Fritts {poll_data.get('fritts','?')}%")
                
            except Exception as e:
                print(f"      ERROR on {poll_url}: {e}")
        
        print(f"    Total polls with governor data: {len(results)}")
        return results
    except Exception as e:
        print(f"    ERROR: {e}")
        return []


def scrape_270towin():
    """Scrape polling data from 270toWin."""
    url = POLLING_URLS[0]
    print(f"  Scraping 270toWin: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        polls = []
        # Look for polling tables - structure varies
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:  # skip header
                cells = row.find_all(["td", "th"])
                if len(cells) >= 4:
                    try:
                        poll = {
                            "pollster": cells[0].get_text(strip=True),
                            "date": cells[1].get_text(strip=True),
                            "results_raw": [c.get_text(strip=True) for c in cells[2:]]
                        }
                        polls.append(poll)
                    except:
                        continue
        
        print(f"    Found {len(polls)} poll entries")
        return polls
    except Exception as e:
        print(f"    ERROR: {e}")
        return []


def scrape_ballotpedia():
    """Scrape candidate and polling info from Ballotpedia."""
    url = POLLING_URLS[1]
    print(f"  Scraping Ballotpedia: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Extract candidate lists from infoboxes
        candidates = {"rep": [], "dem": [], "ind": []}
        
        # Look for candidate sections
        for heading in soup.find_all(["h2", "h3", "h4"]):
            text = heading.get_text(strip=True).lower()
            if "republican" in text:
                party = "rep"
            elif "democrat" in text:
                party = "dem"
            elif "independent" in text or "third" in text:
                party = "ind"
            else:
                continue
            
            # Get the list following this heading
            next_el = heading.find_next(["ul", "table"])
            if next_el and next_el.name == "ul":
                for li in next_el.find_all("li"):
                    name = li.get_text(strip=True)
                    if name and len(name) < 100:
                        candidates[party].append(name)
        
        print(f"    Found candidates: R={len(candidates['rep'])}, D={len(candidates['dem'])}, I={len(candidates['ind'])}")
        return candidates
    except Exception as e:
        print(f"    ERROR: {e}")
        return {}


def scrape_sos_candidates():
    """Scrape TN Secretary of State candidate filings."""
    print(f"  Scraping TN SOS: {SOS_CANDIDATE_URL}")
    try:
        resp = requests.get(SOS_CANDIDATE_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        candidates = []
        # Look for governor section
        for table in soup.find_all("table"):
            header = table.find_previous(["h2", "h3", "h4"])
            if header and "governor" in header.get_text(strip=True).lower():
                rows = table.find_all("tr")
                for row in rows[1:]:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        candidates.append({
                            "name": cells[0].get_text(strip=True),
                            "party": cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        })
        
        print(f"    Found {len(candidates)} filed candidates")
        return candidates
    except Exception as e:
        print(f"    ERROR: {e}")
        return []


def run():
    """Main entry point."""
    print("=" * 60)
    print("TNFirefly Governor Race - Polls & Candidates Scraper")
    print(f"Run time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    
    # Scrape polls
    print("\nScraping TennSight / Beacon Center (primary source)...")
    tennsight_data = scrape_tennsight()
    
    print("\nScraping 270toWin (supplemental)...")
    raw_polls = scrape_270towin()
    
    # Scrape candidates from Ballotpedia
    print("\nScraping Ballotpedia candidates...")
    bp_candidates = scrape_ballotpedia()
    
    # Scrape SOS filings
    print("\nScraping TN Secretary of State...")
    sos_candidates = scrape_sos_candidates()
    
    # Update polls.json - merge with existing
    if POLLS_FILE.exists():
        with open(POLLS_FILE, "r") as f:
            polls_data = json.load(f)
    else:
        polls_data = {"polls": [], "raceRatings": []}
    
    polls_data["lastUpdated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    polls_data["lastScraped"] = datetime.now(timezone.utc).isoformat()
    
    if raw_polls:
        polls_data["scraped_raw"] = raw_polls
    
    if tennsight_data:
        polls_data["tennsight_scraped"] = tennsight_data
    
    with open(POLLS_FILE, "w") as f:
        json.dump(polls_data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved polls data to: {POLLS_FILE}")
    
    # Update candidates.json if we got SOS data
    if sos_candidates or bp_candidates:
        if CANDIDATES_FILE.exists():
            with open(CANDIDATES_FILE, "r") as f:
                cand_data = json.load(f)
        else:
            cand_data = {}
        
        cand_data["lastUpdated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cand_data["lastScraped"] = datetime.now(timezone.utc).isoformat()
        if sos_candidates:
            cand_data["sos_filings"] = sos_candidates
        if bp_candidates:
            cand_data["ballotpedia"] = bp_candidates
        
        with open(CANDIDATES_FILE, "w") as f:
            json.dump(cand_data, f, indent=2, ensure_ascii=False)
        print(f"Saved candidates data to: {CANDIDATES_FILE}")
    
    print("\nDone!")


if __name__ == "__main__":
    run()
