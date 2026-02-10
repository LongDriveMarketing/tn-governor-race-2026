#!/usr/bin/env python3
"""
TNFirefly Governor Race - Comprehensive Polls Scraper
=====================================================
Scrapes polling data from ALL available sources:
  1. Wikipedia - structured polling tables (backbone source)
  2. Beacon Center / TennSight - primary polls, approvals, issue polling
  3. Vanderbilt Poll - approvals, issue polling, political environment
  4. 270toWin - aggregated poll data
  5. RealClearPolling - poll averages
  6. Ballotpedia - race ratings, candidate info
  7. Race ratings from multiple forecasters

Runs every 6 hours via GitHub Actions.
Merges new data with existing polls.json, preserving manual entries.
"""

import sys
import io
import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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

from config import POLLING_SOURCES

DATA_DIR = Path(__file__).parent.parent / "data"
SCRAPED_DIR = DATA_DIR / "scraped"
SCRAPED_DIR.mkdir(exist_ok=True)
POLLS_FILE = SCRAPED_DIR / "polls.json"

HEADERS = {
    "User-Agent": "TNFirefly-GovernorTracker/2.0 (info@tnfirefly.com)"
}

# ─── Utility Functions ───────────────────────────────────────

def make_poll_id(pollster, date, poll_type):
    """Generate a stable unique ID for a poll entry."""
    raw = f"{pollster}-{date}-{poll_type}".lower()
    raw = re.sub(r'[^a-z0-9-]', '-', raw)
    raw = re.sub(r'-+', '-', raw).strip('-')
    return raw


def fetch_page(url, timeout=20):
    """Fetch a page with error handling. Returns BeautifulSoup or None."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"    ERROR fetching {url}: {e}")
        return None


def fetch_text(url, timeout=20):
    """Fetch raw text content of a page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"    ERROR fetching {url}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# SOURCE 1: WIKIPEDIA - Structured polling tables
# ═══════════════════════════════════════════════════════════════

WIKI_URL = "https://en.wikipedia.org/wiki/2026_Tennessee_gubernatorial_election"

def scrape_wikipedia():
    """
    Scrape Wikipedia's structured polling tables for:
    - Republican primary polls
    - General election hypothetical polls
    - Race ratings
    Returns dict with polls, generalPolls, raceRatings
    """
    print("\n  [WIKIPEDIA] Scraping structured polling tables...")
    soup = fetch_page(WIKI_URL)
    if not soup:
        return {"polls": [], "generalPolls": [], "raceRatings": []}

    polls = []
    general_polls = []
    race_ratings = []

    # Find all wikitables
    tables = soup.find_all("table", class_="wikitable")
    print(f"    Found {len(tables)} wikitables")

    for table in tables:
        # Determine table type by looking at preceding headers and content
        prev_heading = None
        for sibling in table.previous_siblings:
            if sibling.name in ["h2", "h3", "h4", "span"]:
                prev_heading = sibling.get_text(strip=True).lower()
                break
            # Also check parent elements for span ids
            if hasattr(sibling, 'find_all') and sibling.name is not None:
                span = sibling.find("span", class_="mw-headline")
                if span:
                    prev_heading = span.get_text(strip=True).lower()
                    break

        headers = []
        header_row = table.find("tr")
        if header_row:
            headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]

        header_text = " ".join(headers)

        # ── Race Ratings Table ──
        # Wikipedia race ratings table has headers: "Source", "Ranking", "As of"
        is_ratings_table = ("source" in header_text and "ranking" in header_text) or \
                           ("source" in header_text and "as of" in header_text) or \
                           any(x in header_text for x in ["cook", "sabato", "crystal ball", "inside elections"])
        
        if is_ratings_table:
            print("    -> Found race ratings table")
            rows = table.find_all("tr")
            for row in rows[1:]:  # skip header
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    source = cells[0].get_text(strip=True)
                    # Find the rating and date from remaining cells
                    rating = ""
                    as_of = ""
                    for cell in cells[1:]:
                        text = cell.get_text(strip=True)
                        if any(r in text.lower() for r in ["solid", "safe", "likely", "lean", "toss"]):
                            rating = text
                        elif re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d', text, re.IGNORECASE):
                            as_of = text
                        elif re.search(r'\d{4}', text) and not rating:
                            as_of = text

                    if source and rating:
                        race_ratings.append({
                            "source": source,
                            "rating": rating,
                            "asOf": as_of,
                            "scrapedFrom": "wikipedia"
                        })
            continue

        # ── Polling Tables ──
        # Detect if this is a primary or general election table
        is_general = False
        is_primary = False

        # Method 1: Walk up to find the nearest section heading (h2/h3/h4 with mw-headline span)
        context_text = ""
        el = table
        for _ in range(30):
            el = el.previous_sibling if el else None
            if el is None:
                # Try parent's previous siblings
                break
            if hasattr(el, 'name') and el.name in ["h2", "h3", "h4"]:
                heading_text = el.get_text(strip=True).lower()
                context_text = heading_text
                break
            if hasattr(el, 'find') and hasattr(el, 'name') and el.name is not None:
                span = el.find("span", class_="mw-headline")
                if span:
                    context_text = span.get_text(strip=True).lower()
                    break
            if hasattr(el, 'get_text') and hasattr(el, 'name') and el.name is not None:
                t = el.get_text(strip=True).lower()
                if len(t) < 200:
                    context_text += t + " "

        # Method 2: Check candidate columns - if has (R) and (D) it's general
        has_party_labels = any("(r)" in h or "(d)" in h for h in headers)
        
        # Method 3: Check for "vs" pattern in nearby text (general election matchups)
        has_vs = "vs." in context_text or "vs " in context_text or " v. " in context_text
        
        if "general" in context_text or has_vs or has_party_labels:
            is_general = True
        elif "primary" in context_text or "republican" in context_text:
            is_primary = True
        elif any(x in header_text for x in ["blackburn", "rose", "fritts"]):
            # If columns have primary candidates without party labels, it's a primary
            is_primary = True

        # Check if table has polling data columns (dates, percentages)
        if not any(x in header_text for x in ["poll", "date", "sample", "margin"]):
            continue

        print(f"    -> Found polling table ({'general' if is_general else 'primary' if is_primary else 'unknown'})")

        # Parse header to find candidate columns
        candidate_cols = {}
        for i, h in enumerate(headers):
            h_clean = h.strip()
            # Known candidates
            if "blackburn" in h_clean:
                candidate_cols[i] = ("Blackburn", "rep")
            elif "rose" in h_clean:
                candidate_cols[i] = ("Rose", "rep")
            elif "fritts" in h_clean:
                candidate_cols[i] = ("Fritts", "rep")
            elif "pellegra" in h_clean:
                candidate_cols[i] = ("Pellegra", "rep")
            elif "green" in h_clean and "mark" not in h_clean:
                candidate_cols[i] = ("Green", "dem")
            elif "atwater" in h_clean:
                candidate_cols[i] = ("Atwater", "dem")
            elif "undecided" in h_clean or "unsure" in h_clean:
                candidate_cols[i] = ("Undecided", "")
            elif "other" in h_clean:
                candidate_cols[i] = ("Other", "")
            elif "margin" in h_clean:
                pass  # skip margin column

        rows = table.find_all("tr")
        for row in rows[1:]:  # skip header
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue

            # Extract poll info from row
            row_texts = [c.get_text(strip=True) for c in cells]

            # Find pollster (usually first or second column)
            pollster = ""
            date_str = ""
            end_date_str = ""
            sample = ""
            margin = ""

            for i, text in enumerate(row_texts):
                if not text:
                    continue
                # Pollster: usually has letters and possibly brackets
                if re.search(r'[A-Za-z].*(?:Research|Poll|Insight|Associat|Lee|Targoz|Quantus|Beacon|Vanderb|MTSU)', text, re.IGNORECASE):
                    pollster = text
                # Date pattern: Month DD, YYYY or similar
                elif re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', text, re.IGNORECASE):
                    if not date_str:
                        date_str = text
                # Sample size
                elif re.search(r'\d+\s*(?:\(|RV|LV|A)', text):
                    sample = text
                # Margin
                elif re.search(r'±|%', text) and len(text) < 15 and i > 0:
                    if not any(text.replace('%','').replace('–','').replace('−','').strip().isdigit() for _ in [1]):
                        margin = text

            if not pollster:
                continue

            # Parse dates
            start_date = ""
            end_date = ""
            date_matches = re.findall(r'(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s*\d{4})', date_str)
            if date_matches:
                try:
                    end_part = date_matches[0][1]
                    year_match = re.search(r'\d{4}', end_part)
                    year = year_match.group() if year_match else "2025"
                    start_part = date_matches[0][0] + ", " + year
                    start_dt = None
                    for fmt in ["%B %d, %Y", "%b %d, %Y"]:
                        try:
                            start_dt = datetime.strptime(start_part, fmt)
                            break
                        except ValueError:
                            continue
                    end_dt = None
                    for fmt in ["%B %d, %Y", "%b %d, %Y"]:
                        try:
                            end_dt = datetime.strptime(end_part.strip().rstrip(','), fmt)
                            break
                        except ValueError:
                            # Try adding year
                            try:
                                end_dt = datetime.strptime(end_part.strip().rstrip(',') + " " + year, fmt)
                                break
                            except ValueError:
                                continue
                    if start_dt:
                        start_date = start_dt.strftime("%Y-%m-%d")
                    if end_dt:
                        end_date = end_dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

            if not start_date:
                # Try simpler date extraction
                simple_date = re.search(r'(\w+)\s+(\d{1,2}),?\s*(\d{4})', date_str)
                if simple_date:
                    try:
                        dt = datetime.strptime(f"{simple_date.group(1)} {simple_date.group(2)}, {simple_date.group(3)}", "%B %d, %Y")
                        start_date = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        try:
                            dt = datetime.strptime(f"{simple_date.group(1)} {simple_date.group(2)}, {simple_date.group(3)}", "%b %d, %Y")
                            start_date = dt.strftime("%Y-%m-%d")
                        except ValueError:
                            pass

            # Extract candidate percentages
            results = []
            for col_idx, (cand_name, cand_party) in candidate_cols.items():
                if col_idx < len(row_texts):
                    pct_text = row_texts[col_idx]
                    pct_match = re.search(r'(\d+(?:\.\d+)?)', pct_text.replace('%', ''))
                    if pct_match:
                        results.append({
                            "candidate": cand_name,
                            "party": cand_party,
                            "pct": float(pct_match.group(1))
                        })

            if results and pollster:
                poll_type = "general_hypothetical" if is_general else "republican_primary"
                poll_id = make_poll_id(pollster, start_date or "unknown", poll_type)

                poll_entry = {
                    "id": poll_id,
                    "pollster": pollster,
                    "pollsterLean": "",
                    "date": start_date,
                    "endDate": end_date or start_date,
                    "type": poll_type,
                    "sampleSize": sample,
                    "margin": margin,
                    "results": results,
                    "source": "wikipedia",
                    "url": WIKI_URL + "#Opinion_polling"
                }

                # Set pollster lean
                if "quantus" in pollster.lower():
                    poll_entry["pollsterLean"] = "R"
                elif "fabrizio" in pollster.lower():
                    poll_entry["pollsterLean"] = "R"

                if is_general:
                    # Try to detect matchup
                    cands = [r["candidate"] for r in results if r["party"]]
                    if len(cands) >= 2:
                        poll_entry["matchup"] = " vs ".join(cands[:2])
                    general_polls.append(poll_entry)
                else:
                    polls.append(poll_entry)

    print(f"    Wikipedia results: {len(polls)} primary polls, {len(general_polls)} general polls, {len(race_ratings)} ratings")
    return {
        "polls": polls,
        "generalPolls": general_polls,
        "raceRatings": race_ratings
    }


# ═══════════════════════════════════════════════════════════════
# SOURCE 2: BEACON CENTER / TENNSIGHT
# ═══════════════════════════════════════════════════════════════

TENNSIGHT_POLLS_URL = "https://tennsight.com/polls/"
TENNSIGHT_ELECTIONS_URL = "https://tennsight.com/elections/"

def scrape_tennsight():
    """
    Scrape TennSight poll pages for:
    - Governor race primary numbers
    - Approval ratings (Lee, Legislature, Trump)
    - Issue polling (school choice, education)
    Returns dict with approval_ratings, issue_polling, primary_data
    """
    print("\n  [TENNSIGHT] Scraping Beacon Center polls...")
    
    approvals = []
    issues = []
    
    # First get the polls index to find all poll page URLs
    soup = fetch_page(TENNSIGHT_POLLS_URL)
    if not soup:
        return {"approvals": [], "issues": []}
    
    # Find links to individual poll pages
    poll_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/polls/' in href and re.search(r'(?:january|february|march|april|may|june|july|august|september|october|november|december)-\d{4}', href):
            full_url = href if href.startswith('http') else f"https://tennsight.com{href}"
            if full_url not in poll_links:
                poll_links.append(full_url)
    
    print(f"    Found {len(poll_links)} poll pages")
    
    # Scrape each poll page (last 6 max to stay current)
    for poll_url in poll_links[:6]:
        try:
            print(f"    Checking: {poll_url}")
            psoup = fetch_page(poll_url)
            if not psoup:
                continue
            ptext = psoup.get_text()
            
            # Extract poll name from URL
            poll_name_match = re.search(r'/polls/([^/]+)/?', poll_url)
            poll_name = poll_name_match.group(1) if poll_name_match else "unknown"
            
            # ── Governor Lee Approval ──
            # TennSight uses patterns like: "Governor Lee...with a +25% spread (59%-34%)"
            # or "59% of voters approve of Governor Lee"
            lee_approve = None
            lee_disapprove_val = None
            
            # Pattern 1: spread format "(59%-34%)"
            lee_spread = re.search(r'(?:Governor|Gov\.?\s+)(?:Bill\s+)?Lee.*?\((\d+)%\s*[-\u2013]\s*(\d+)%\)', ptext, re.IGNORECASE)
            if lee_spread:
                lee_approve = int(lee_spread.group(1))
                lee_disapprove_val = int(lee_spread.group(2))
            
            # Pattern 2: "X% approve...Governor Lee" or "Governor Lee...X% approval"  
            if not lee_approve:
                m = re.search(r'(\d+)\s*(?:percent|%)\s*(?:of\s+)?(?:Tennessee\s+)?(?:registered\s+)?(?:voters?\s+)?(?:approv|say\s+they\s+approv).*?(?:Governor|Gov\.?\s+)Lee', ptext, re.IGNORECASE)
                if not m:
                    m = re.search(r'(?:Governor|Gov\.?\s+)Lee.*?(\d+)\s*(?:percent|%)\s*(?:approv|approval)', ptext, re.IGNORECASE)
                if m:
                    lee_approve = int(m.group(1))
            
            # Pattern 3: disapprove separate
            if lee_approve and not lee_disapprove_val:
                m = re.search(r'(\d+)\s*(?:percent|%)\s*disapprov.*?(?:Governor|Gov\.?\s+)Lee', ptext, re.IGNORECASE)
                if m:
                    lee_disapprove_val = int(m.group(1))
            
            if lee_approve:
                entry = {
                    "subject": "Governor Lee",
                    "approve": lee_approve,
                    "poll": poll_name,
                    "source": "Beacon Center / TennSight",
                    "url": poll_url
                }
                if lee_disapprove_val:
                    entry["disapprove"] = lee_disapprove_val
                approvals.append(entry)
                print(f"      -> Lee approval: {lee_approve}%")
            
            # ── Trump Approval ──
            trump_approve = re.search(r'(\d+)\s*(?:percent|%)\s*(?:of\s+)?(?:Tennessee\s+)?(?:voters?\s+)?approv.*?(?:President\s+)?Trump', ptext, re.IGNORECASE)
            if not trump_approve:
                trump_approve = re.search(r'Trump.*?(\d+)\s*(?:percent|%)\s*approv', ptext, re.IGNORECASE)
            if not trump_approve:
                trump_approve = re.search(r'Trump.*?\((\d+)%\s*[-\u2013]\s*(\d+)%\)', ptext, re.IGNORECASE)
            trump_disapprove = re.search(r'(\d+)\s*(?:percent|%)\s*disapprov.*?Trump', ptext, re.IGNORECASE)
            
            if trump_approve:
                entry = {
                    "subject": "President Trump",
                    "approve": int(trump_approve.group(1)),
                    "poll": poll_name,
                    "source": "Beacon Center / TennSight",
                    "url": poll_url
                }
                if trump_disapprove:
                    entry["disapprove"] = int(trump_disapprove.group(1))
                approvals.append(entry)
                print(f"      -> Trump approval: {entry['approve']}%")
            
            # ── Legislature Approval ──
            leg_approve = re.search(r'(\d+)\s*(?:percent|%)\s*(?:of\s+)?(?:voters?\s+)?approv.*?(?:legislature|General Assembly|state\s+legislat)', ptext, re.IGNORECASE)
            if not leg_approve:
                leg_approve = re.search(r'(?:legislature|General Assembly).*?(\d+)\s*(?:percent|%)\s*approv', ptext, re.IGNORECASE)
            
            if leg_approve:
                entry = {
                    "subject": "TN Legislature",
                    "approve": int(leg_approve.group(1)),
                    "poll": poll_name,
                    "source": "Beacon Center / TennSight",
                    "url": poll_url
                }
                approvals.append(entry)
                print(f"      -> Legislature approval: {entry['approve']}%")
            
            # ── Senator Blackburn Favorability ──
            bb_approve = None
            bb_spread = re.search(r'(?:Senator\s+)?(?:Marsha\s+)?Blackburn.*?\(([+-]?\d+)%\)', ptext, re.IGNORECASE)
            if not bb_spread:
                bb_approve_m = re.search(r'(?:Senator\s+)?(?:Marsha\s+)?Blackburn.*?(\d+)\s*(?:percent|%)\s*(?:favorab|approv)', ptext, re.IGNORECASE)
                if bb_approve_m:
                    bb_approve = int(bb_approve_m.group(1))
            
            # Try to get her R/D/I breakdown favorability
            bb_among_r = re.search(r'Blackburn.*?(?:among\s+)?Republicans.*?\(([+-]?\d+)%\)', ptext, re.IGNORECASE)
            
            if bb_approve:
                approvals.append({
                    "subject": "Senator Blackburn",
                    "approve": bb_approve,
                    "poll": poll_name,
                    "source": "Beacon Center / TennSight",
                    "url": poll_url
                })
                print(f"      -> Blackburn favorability: {bb_approve}%")
            
            # ── School Choice / Education Issues ──
            school_choice = re.search(r'(\d+)\s*(?:percent|%)\s*(?:of\s+)?(?:voters?\s+)?(?:support|favor).*?(?:school\s+choice|tax\s+credit|voucher|Education\s+Freedom\s+Scholarship)', ptext, re.IGNORECASE)
            if school_choice:
                issues.append({
                    "topic": "School Choice / Tax Credit",
                    "support": int(school_choice.group(1)),
                    "poll": poll_name,
                    "source": "Beacon Center / TennSight",
                    "url": poll_url
                })
                print(f"      -> School choice support: {school_choice.group(1)}%")
            
            # ── Education Satisfaction ──
            ed_satisfy = re.search(r'(\d+)\s*(?:percent|%)\s*(?:of\s+)?(?:voters?\s+)?(?:are\s+)?(?:satisfied|happy|pleased).*?(?:education|schools|public\s+school)', ptext, re.IGNORECASE)
            if ed_satisfy:
                issues.append({
                    "topic": "Education Satisfaction",
                    "support": int(ed_satisfy.group(1)),
                    "poll": poll_name,
                    "source": "Beacon Center / TennSight",
                    "url": poll_url
                })
            
            # ── Right Direction / Wrong Track ──
            right_track = re.search(r'(\d+)\s*(?:percent|%)\s*(?:of\s+)?(?:voters?\s+)?(?:say|think|believe)?\s*(?:Tennessee\s+is\s+)?(?:head|going|on)\s*(?:ed\s+)?(?:in\s+)?(?:the\s+)?right\s+direction', ptext, re.IGNORECASE)
            if right_track:
                issues.append({
                    "topic": "Tennessee Right Direction",
                    "value": int(right_track.group(1)),
                    "poll": poll_name,
                    "source": "Beacon Center / TennSight",
                    "url": poll_url
                })
            
        except Exception as e:
            print(f"      ERROR on {poll_url}: {e}")
    
    print(f"    TennSight results: {len(approvals)} approval ratings, {len(issues)} issue polls")
    return {"approvals": approvals, "issues": issues}


# ═══════════════════════════════════════════════════════════════
# SOURCE 3: VANDERBILT POLL
# ═══════════════════════════════════════════════════════════════

VANDERBILT_NEWS_URL = "https://news.vanderbilt.edu/?s=vanderbilt+poll"
VANDERBILT_CSDI_URL = "https://www.vanderbilt.edu/csdi/vupoll-home.php"

def scrape_vanderbilt():
    """
    Scrape Vanderbilt Poll news releases for:
    - Approval ratings (Lee, Blackburn, Trump, Legislature)
    - Political environment (right track, MAGA identification)
    - Issue polling (education, IVF, abortion, school choice)
    - Any governor race matchup data
    """
    print("\n  [VANDERBILT] Scraping Vanderbilt Poll news releases...")
    
    approvals = []
    issues = []
    environment = []
    
    # Search for recent Vanderbilt Poll articles
    soup = fetch_page(VANDERBILT_NEWS_URL)
    if not soup:
        return {"approvals": [], "issues": [], "environment": []}
    
    # Find article links
    article_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'news.vanderbilt.edu' in href and 'vanderbilt-poll' in href.lower():
            if href not in article_links and '#' not in href:
                article_links.append(href)
    
    # Also check CSDI page for direct links
    csdi_soup = fetch_page(VANDERBILT_CSDI_URL)
    if csdi_soup:
        for a in csdi_soup.find_all('a', href=True):
            href = a['href']
            if 'vanderbilt-poll' in href.lower() and href not in article_links:
                article_links.append(href)
    
    print(f"    Found {len(article_links)} Vanderbilt Poll articles")
    
    # Process last 4 articles (covers ~2 years of semiannual polls)
    for article_url in article_links[:4]:
        try:
            print(f"    Reading: {article_url}")
            asoup = fetch_page(article_url)
            if not asoup:
                continue
            atext = asoup.get_text()
            
            # Detect poll date from article
            # Look for patterns like "April 17 to April 27" or "spring 2025" etc.
            poll_period = ""
            period_match = re.search(r'(?:spring|fall|summer|winter)\s+\d{4}', atext, re.IGNORECASE)
            if period_match:
                poll_period = period_match.group()
            else:
                # Try date range
                date_range = re.search(r'(?:from\s+)?(\w+ \d+)\s+(?:to|through|-)\s+(\w+ \d+)', atext, re.IGNORECASE)
                if date_range:
                    poll_period = f"{date_range.group(1)} - {date_range.group(2)}"
            
            # Date from URL or article date
            year_match = re.search(r'/(\d{4})/(\d{2})/', article_url)
            article_year = year_match.group(1) if year_match else ""
            
            # ── Governor Lee Approval ──
            lee_patterns = [
                r'(?:Governor|Gov\.?)\s+(?:Bill\s+)?Lee.*?(\d+)\s*(?:percent|%)\s*(?:of\s+)?(?:Tennesseans?\s+)?(?:survey|approv)',
                r'(\d+)\s*(?:percent|%)\s*(?:of\s+)?Tennesseans?\s+(?:survey|approv).*?(?:Governor|Gov)',
                r'(?:Governor|Gov)\s+Lee\s+(?:enjoys?\s+)?(?:a\s+)?(?:net\s+positive\s+)?(?:rating|approval).*?(\d+)\s*(?:percent|%)',
                r'approv.*?(?:Governor|Gov).*?(?:is\s+)?(\d+)\s*(?:percent|%)',
            ]
            for pattern in lee_patterns:
                m = re.search(pattern, atext, re.IGNORECASE)
                if m:
                    approvals.append({
                        "subject": "Governor Lee",
                        "approve": int(m.group(1)),
                        "poll": poll_period,
                        "source": "Vanderbilt Poll",
                        "url": article_url
                    })
                    print(f"      -> Lee approval: {m.group(1)}%")
                    break
            
            # ── Blackburn Approval ──
            bb_match = re.search(r'(?:Senator\s+)?(?:Marsha\s+)?Blackburn.{0,80}?(\d+)\s*(?:percent|%)\s*(?:approv|approval)', atext, re.IGNORECASE)
            if not bb_match:
                bb_match = re.search(r'Blackburn.{0,40}?approv.*?(?:from\s+)?(\d+)\s*(?:percent|%)', atext, re.IGNORECASE)
            if bb_match:
                approvals.append({
                    "subject": "Senator Blackburn",
                    "approve": int(bb_match.group(1)),
                    "poll": poll_period,
                    "source": "Vanderbilt Poll",
                    "url": article_url
                })
                print(f"      -> Blackburn approval: {bb_match.group(1)}%")
            
            # ── Trump Approval ──
            trump_match = re.search(r'(?:President\s+)?(?:Donald\s+)?Trump.{0,60}?approv.*?(\d+)\s*(?:percent|%)', atext, re.IGNORECASE)
            if not trump_match:
                trump_match = re.search(r'Trump.{0,40}?(\d+)\s*(?:percent|%)', atext, re.IGNORECASE)
            if trump_match:
                approvals.append({
                    "subject": "President Trump",
                    "approve": int(trump_match.group(1)),
                    "poll": poll_period,
                    "source": "Vanderbilt Poll",
                    "url": article_url
                })
                print(f"      -> Trump approval: {trump_match.group(1)}%")
            
            # ── Legislature Approval ──
            leg_match = re.search(r'(?:Tennessee\s+)?(?:State\s+)?Legislatur.*?(\d+)\s*(?:percent|%)\s*(?:approv|approval)', atext, re.IGNORECASE)
            if not leg_match:
                leg_match = re.search(r'(\d+)\s*(?:percent|%)\s*approv.*?(?:legislature|Congress)', atext, re.IGNORECASE)
            if leg_match:
                approvals.append({
                    "subject": "TN Legislature",
                    "approve": int(leg_match.group(1)),
                    "poll": poll_period,
                    "source": "Vanderbilt Poll",
                    "url": article_url
                })
                print(f"      -> Legislature approval: {leg_match.group(1)}%")
            
            # ── Right Direction ──
            rt_match = re.search(r'(\d+)\s*(?:percent|%)\s*(?:of\s+)?(?:Tennesseans?\s+)?(?:said?\s+)?(?:the\s+)?(?:state|Tennessee)\s+(?:is\s+)?(?:head|going|on).*?right\s+(?:direction|track)', atext, re.IGNORECASE)
            if rt_match:
                environment.append({
                    "metric": "Tennessee Right Track",
                    "value": int(rt_match.group(1)),
                    "poll": poll_period,
                    "source": "Vanderbilt Poll",
                    "url": article_url
                })
            
            # ── MAGA Identification ──
            maga_match = re.search(r'(\d+)\s*(?:percent|%)\s*(?:in\s+)?(?:those\s+)?(?:who\s+)?(?:identify|view\s+themselves|supporter\s+of)\s*(?:as\s+)?.*?MAGA', atext, re.IGNORECASE)
            if maga_match:
                environment.append({
                    "metric": "MAGA Identification (among R)",
                    "value": int(maga_match.group(1)),
                    "poll": poll_period,
                    "source": "Vanderbilt Poll",
                    "url": article_url
                })
            
            # ── Education Priority ──
            ed_match = re.search(r'(?:education|K-12|public\s+school).*?(\d+)\s*(?:percent|%)\s*(?:of\s+)?(?:voters?\s+)?(?:say|rank|consider|priority)', atext, re.IGNORECASE)
            if ed_match:
                issues.append({
                    "topic": "Education Priority",
                    "value": int(ed_match.group(1)),
                    "poll": poll_period,
                    "source": "Vanderbilt Poll",
                    "url": article_url
                })
            
            # ── School Vouchers ──
            voucher_match = re.search(r'(?:school\s+voucher|voucher).*?(\d+)\s*(?:percent|%)\s*(?:support|favor|approve)', atext, re.IGNORECASE)
            if voucher_match:
                issues.append({
                    "topic": "School Vouchers",
                    "value": int(voucher_match.group(1)),
                    "poll": poll_period,
                    "source": "Vanderbilt Poll",
                    "url": article_url
                })
            
            # ── Pro-Choice / Abortion ──
            prochoice_match = re.search(r'(\d+)\s*(?:percent|%)\s*(?:of\s+)?(?:voters?\s+)?(?:consider\s+themselves?\s+)?(?:definitely\s+or\s+somewhat\s+)?pro.?choice', atext, re.IGNORECASE)
            if prochoice_match:
                issues.append({
                    "topic": "Pro-Choice Identification",
                    "value": int(prochoice_match.group(1)),
                    "poll": poll_period,
                    "source": "Vanderbilt Poll",
                    "url": article_url
                })
            
            # ── IVF Support ──
            ivf_match = re.search(r'(\d+)\s*(?:percent|%)\s*(?:of\s+)?(?:voters?\s+)?(?:said?\s+that?\s+)?(?:IVF|in\s+vitro).*?(?:should\s+be\s+)?legal', atext, re.IGNORECASE)
            if ivf_match:
                issues.append({
                    "topic": "IVF Legality Support",
                    "value": int(ivf_match.group(1)),
                    "poll": poll_period,
                    "source": "Vanderbilt Poll",
                    "url": article_url
                })
            
        except Exception as e:
            print(f"      ERROR on {article_url}: {e}")
    
    print(f"    Vanderbilt results: {len(approvals)} approvals, {len(issues)} issue polls, {len(environment)} environment")
    return {"approvals": approvals, "issues": issues, "environment": environment}


# ═══════════════════════════════════════════════════════════════
# SOURCE 4: 270toWIN
# ═══════════════════════════════════════════════════════════════

TOWIN_URL = "https://www.270towin.com/2026-governor-polls/tennessee"

def scrape_270towin():
    """Scrape 270toWin polling table for any polls not in Wikipedia."""
    print("\n  [270toWin] Scraping aggregated polls...")
    soup = fetch_page(TOWIN_URL)
    if not soup:
        return {"hasData": False, "url": TOWIN_URL, "rawPolls": []}

    raw_polls = []
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 4:
                raw = [c.get_text(strip=True) for c in cells]
                raw_polls.append({
                    "source": "270toWin",
                    "raw": raw,
                    "url": TOWIN_URL
                })

    print(f"    270toWin: {len(raw_polls)} poll entries")
    return {
        "hasData": len(raw_polls) > 0,
        "url": TOWIN_URL,
        "rawPolls": raw_polls
    }


# ═══════════════════════════════════════════════════════════════
# SOURCE 5: REALCLEARPOLLING
# ═══════════════════════════════════════════════════════════════

RCP_URLS = {
    "primary": "https://www.realclearpolling.com/polls/governor/republican-primary/2026/tennessee",
    "general": "https://www.realclearpolling.com/polls/governor/general/2026/tennessee"
}

def scrape_realclearpolling():
    """Check RealClearPolling for aggregated data. Often JS-rendered."""
    print("\n  [RCP] Checking RealClearPolling...")
    raw_polls = []
    
    for label, url in RCP_URLS.items():
        soup = fetch_page(url)
        if not soup:
            continue
        
        # RCP uses dynamic JS tables, but check for any static content
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 3:
                    raw = [c.get_text(strip=True) for c in cells]
                    raw_polls.append({
                        "source": "RealClearPolling",
                        "type": label,
                        "raw": raw,
                        "url": url
                    })
    
    print(f"    RCP: {len(raw_polls)} entries (note: may be JS-rendered)")
    return {
        "hasData": len(raw_polls) > 0,
        "url": RCP_URLS["primary"],
        "rawPolls": raw_polls
    }


# ═══════════════════════════════════════════════════════════════
# DATA MERGING & DEDUPLICATION
# ═══════════════════════════════════════════════════════════════

def merge_polls(existing, new_polls):
    """
    Merge new poll entries into existing list, deduplicating by ID.
    New entries with same ID overwrite old ones (fresher data).
    """
    existing_ids = {p.get("id", ""): i for i, p in enumerate(existing)}
    merged = list(existing)
    
    for poll in new_polls:
        pid = poll.get("id", "")
        if pid and pid in existing_ids:
            # Update existing entry
            merged[existing_ids[pid]] = poll
        else:
            merged.append(poll)
    
    # Sort by date descending
    merged.sort(key=lambda p: p.get("date", "0000"), reverse=True)
    return merged


def merge_list_by_key(existing, new_items, key_fields):
    """
    Merge lists using composite key (e.g., subject+poll+source for approvals).
    """
    def make_key(item):
        return "|".join(str(item.get(f, "")) for f in key_fields)
    
    existing_keys = {make_key(item): i for i, item in enumerate(existing)}
    merged = list(existing)
    
    for item in new_items:
        k = make_key(item)
        if k in existing_keys:
            merged[existing_keys[k]] = item  # Update
        else:
            merged.append(item)
    
    return merged


def build_trendline(polls):
    """Generate trendline data from primary polls."""
    trendline = []
    for poll in sorted(polls, key=lambda p: p.get("date", "0000")):
        if poll.get("type") != "republican_primary":
            continue
        entry = {"date": poll["date"], "pollster": poll.get("pollster", "")}
        for r in poll.get("results", []):
            cand = r["candidate"].lower()
            if cand in ["blackburn", "rose", "fritts", "other", "undecided"]:
                entry[cand] = r["pct"]
        if "blackburn" in entry:
            trendline.append(entry)
    
    # Generate description
    if len(trendline) >= 2:
        first = trendline[0]
        last = trendline[-1]
        bb_start = first.get("blackburn", 0)
        bb_end = last.get("blackburn", 0)
        change = bb_end - bb_start
        desc = (
            f"Across {len(trendline)} polls from {len(set(t['pollster'] for t in trendline))} pollsters, "
            f"Blackburn's support has moved from {bb_start}% to {bb_end}% "
            f"({'+'if change > 0 else ''}{change:.1f} pts). "
        )
        und_end = last.get("undecided", 0)
        if und_end:
            desc += f"Undecided voters at {und_end}%, representing the key battleground."
    else:
        desc = "Limited polling data available."
    
    return {"description": desc, "data": trendline}


def generate_analysis(polls, general_polls, approvals, race_ratings):
    """Auto-generate analysis text from the data."""
    # Count polls by pollster
    pollsters = set()
    for p in polls:
        pollsters.add(re.sub(r'\[.*?\]', '', p.get("pollster", "")).strip())
    
    latest = polls[0] if polls else None
    
    parts = []
    
    if latest:
        bb_pct = None
        rose_pct = None
        fritts_pct = None
        und_pct = None
        for r in latest.get("results", []):
            if r["candidate"] == "Blackburn":
                bb_pct = r["pct"]
            elif r["candidate"] == "Rose":
                rose_pct = r["pct"]
            elif r["candidate"] == "Fritts":
                fritts_pct = r["pct"]
            elif r["candidate"] == "Undecided":
                und_pct = r["pct"]
        
        parts.append(
            f"With {len(polls)} polls from {len(pollsters)} pollster{'s' if len(pollsters) > 1 else ''} tracking the Republican primary, "
            f"Blackburn leads at {bb_pct}%"
            + (f" over Rose ({rose_pct}%)" if rose_pct else "")
            + (f" and Fritts ({fritts_pct}%)" if fritts_pct else "")
            + "."
        )
        if und_pct and und_pct > 20:
            parts.append(f"The undecided pool remains significant at {und_pct}%.")
    
    # Race ratings
    if race_ratings:
        ratings_summary = ", ".join(f"{r['source'].split('[')[0].strip()}: {r['rating']}" for r in race_ratings[:4])
        parts.append(f"Race ratings: {ratings_summary}.")
    
    # Approval context
    lee_approvals = [a for a in approvals if "Lee" in a.get("subject", "")]
    if lee_approvals:
        latest_lee = lee_approvals[0]
        parts.append(f"Governor Lee's approval: {latest_lee['approve']}% ({latest_lee['source']}).")
    
    return " ".join(parts)


# ═══════════════════════════════════════════════════════════════
# MAIN RUN FUNCTION
# ═══════════════════════════════════════════════════════════════

def run():
    """Main entry point - scrapes all sources and merges into polls.json."""
    print("=" * 60)
    print("TNFirefly Governor Race - Comprehensive Polls Scraper v2.0")
    print(f"Run time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    
    # Load existing data (scraped version, or fall back to main data/ for bootstrap)
    if POLLS_FILE.exists():
        with open(POLLS_FILE, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    elif (DATA_DIR / "polls.json").exists():
        with open(DATA_DIR / "polls.json", "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        print("  (Bootstrap: loaded existing data from data/polls.json)")
    else:
        data = {
            "lastUpdated": "",
            "pollingSources": [],
            "raceRatings": [],
            "polls": [],
            "generalPolls": [],
            "trendline": {},
            "approvalRatings": {},
            "issuePolling": {},
            "politicalEnvironment": {},
            "aggregators": {},
            "analysis": ""
        }
    
    # Track what changed
    changes = []
    
    # ── 1. Wikipedia (backbone - primary + general polls + race ratings) ──
    wiki_data = scrape_wikipedia()
    
    old_poll_count = len(data.get("polls", []))
    data["polls"] = merge_polls(data.get("polls", []), wiki_data["polls"])
    new_poll_count = len(data["polls"])
    if new_poll_count > old_poll_count:
        changes.append(f"+{new_poll_count - old_poll_count} primary polls from Wikipedia")
    
    old_gen_count = len(data.get("generalPolls", []))
    data["generalPolls"] = merge_polls(data.get("generalPolls", []), wiki_data["generalPolls"])
    new_gen_count = len(data["generalPolls"])
    if new_gen_count > old_gen_count:
        changes.append(f"+{new_gen_count - old_gen_count} general polls from Wikipedia")
    
    if wiki_data["raceRatings"]:
        data["raceRatings"] = wiki_data["raceRatings"]
        changes.append(f"Updated {len(wiki_data['raceRatings'])} race ratings")
    
    # ── 2. TennSight / Beacon Center (approvals, issues) ──
    tennsight_data = scrape_tennsight()
    
    # Merge approvals
    all_approvals = []
    for group in data.get("approvalRatings", {}).values():
        all_approvals.extend(group)
    all_approvals = merge_list_by_key(
        all_approvals, 
        tennsight_data.get("approvals", []),
        ["subject", "poll", "source"]
    )
    
    # Merge issues
    all_issues = []
    for group in data.get("issuePolling", {}).values():
        all_issues.extend(group)
    all_issues = merge_list_by_key(
        all_issues,
        tennsight_data.get("issues", []),
        ["topic", "poll", "source"]
    )
    
    ts_approval_count = len(tennsight_data.get("approvals", []))
    ts_issue_count = len(tennsight_data.get("issues", []))
    if ts_approval_count:
        changes.append(f"TennSight: {ts_approval_count} approval ratings")
    if ts_issue_count:
        changes.append(f"TennSight: {ts_issue_count} issue polls")
    
    # ── 3. Vanderbilt Poll (approvals, issues, environment) ──
    vandy_data = scrape_vanderbilt()
    
    all_approvals = merge_list_by_key(
        all_approvals,
        vandy_data.get("approvals", []),
        ["subject", "poll", "source"]
    )
    
    all_issues = merge_list_by_key(
        all_issues,
        vandy_data.get("issues", []),
        ["topic", "poll", "source"]
    )
    
    # Environment data
    all_environment = []
    for group in data.get("politicalEnvironment", {}).values():
        all_environment.extend(group)
    all_environment = merge_list_by_key(
        all_environment,
        vandy_data.get("environment", []),
        ["metric", "poll", "source"]
    )
    
    vandy_count = sum(len(v) for v in vandy_data.values())
    if vandy_count:
        changes.append(f"Vanderbilt: {vandy_count} data points")
    
    # ── 4. 270toWin ──
    towin_data = scrape_270towin()
    data.setdefault("aggregators", {})["twoSeventyToWin"] = towin_data
    
    # ── 5. RealClearPolling ──
    rcp_data = scrape_realclearpolling()
    data.setdefault("aggregators", {})["realClearPolling"] = rcp_data
    
    # ── Reorganize approvals by subject ──
    approval_groups = {}
    for a in all_approvals:
        subj = a.get("subject", "Other")
        approval_groups.setdefault(subj, []).append(a)
    data["approvalRatings"] = approval_groups
    
    # ── Reorganize issues by topic ──
    issue_groups = {}
    for i in all_issues:
        topic = i.get("topic", "Other")
        issue_groups.setdefault(topic, []).append(i)
    data["issuePolling"] = issue_groups
    
    # ── Reorganize environment by metric ──
    env_groups = {}
    for e in all_environment:
        metric = e.get("metric", "Other")
        env_groups.setdefault(metric, []).append(e)
    data["politicalEnvironment"] = env_groups
    
    # ── Rebuild trendline ──
    data["trendline"] = build_trendline(data["polls"])
    
    # ── Auto-generate analysis ──
    flat_approvals = [a for group in approval_groups.values() for a in group]
    data["analysis"] = generate_analysis(
        data["polls"], 
        data["generalPolls"],
        flat_approvals,
        data["raceRatings"]
    )
    
    # ── Update metadata ──
    data["lastUpdated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data["lastScraped"] = datetime.now(timezone.utc).isoformat()
    
    # ── Save ──
    with open(POLLS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("  POLLS SCRAPER RESULTS")
    print("=" * 60)
    print(f"  Primary polls:   {len(data['polls'])}")
    print(f"  General polls:   {len(data['generalPolls'])}")
    print(f"  Race ratings:    {len(data['raceRatings'])}")
    print(f"  Approval groups: {len(data['approvalRatings'])}")
    print(f"  Issue topics:    {len(data['issuePolling'])}")
    print(f"  Environment:     {len(data['politicalEnvironment'])}")
    if changes:
        print(f"  Changes: {'; '.join(changes)}")
    else:
        print(f"  No new data found")
    print(f"  Saved to: {POLLS_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    run()

