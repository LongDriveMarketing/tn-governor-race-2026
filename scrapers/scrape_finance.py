#!/usr/bin/env python3
"""
TNFirefly Governor Race - Campaign Finance Scraper
Source: Tennessee Registry of Election Finance (apps.tn.gov/tncamp)

Scrapes campaign finance disclosure reports for all 2026 governor candidates.
Extracts: total raised, total spent, cash on hand, loans, report dates.
Outputs to data/scraped/finance.json for merge pipeline.
"""

import json
import re
import time
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime, timezone
from pathlib import Path

# ── CONFIG ──
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
SCRAPED_DIR = DATA_DIR / "scraped"
FINANCE_FILE = SCRAPED_DIR / "finance.json"
MAIN_FINANCE = DATA_DIR / "finance.json"

BASE_URL = "https://apps.tn.gov/tncamp"
SEARCH_URL = f"{BASE_URL}/public/cpsearch.htm"
REPORT_URL = f"{BASE_URL}/search/pub/report_full.htm"

# Governor = office 2, 2026 = election year 234
OFFICE_ID = "2"
ELECTION_YEAR_ID = "234"

# Map TN camp names to display names and party codes
NAME_MAP = {
    "BLACKBURN, MARSHA": {"name": "Marsha Blackburn", "party": "rep"},
    "ROSE, JOHN": {"name": "John Rose", "party": "rep"},
    "FRITTS (GOVERNOR), MONTY": {"name": "Monty Fritts", "party": "rep"},
    "PELLEGRA, CITO V.": {"name": "Cito Pellegra", "party": "rep"},
    "SCOGGIN, VICTOR L.": {"name": "Victor Scoggin", "party": "rep"},
    "GREEN, JERRI": {"name": "Jerri Green", "party": "dem"},
    "ATWATER, CARNITA": {"name": "Carnita Atwater", "party": "dem"},
    "KURTZ, ADAM (DITCH)": {"name": "Adam 'Ditch' Kurtz", "party": "dem"},
    "CYR, TIM": {"name": "Tim Cyr", "party": "dem"},
    "DEROSIER, BRANDEE": {"name": "Brandee DeRosier", "party": "dem"},
    "VICK, ROBERT C.": {"name": "Robert Vick", "party": "ind"},
    "PINKSTON, LAUREN": {"name": "Lauren Pinkston", "party": "ind"},
    "MURPHY, EDDIE L.": {"name": "Eddie Murphy", "party": "ind"},
    "MAXWELL, STEPHEN CORTNEY": {"name": "Stephen Maxwell", "party": "ind"},
}

# Only include candidates with significant activity or who are tracked
# Set to None to include ALL candidates
TRACKED_CANDIDATES = None  # Include everyone; merge/manual.json controls what shows on site


def create_opener():
    """Create a URL opener with cookie support."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [
        ('User-Agent', 'TNFirefly-Bot/1.0 (education journalism)'),
        ('Accept', 'text/html'),
    ]
    return opener


def get_session(opener):
    """Initialize session by visiting search page."""
    print("[Finance] Getting session cookie...")
    opener.open(SEARCH_URL, timeout=30)
    time.sleep(1)


def search_candidates(opener):
    """Search for all 2026 governor candidates."""
    print("[Finance] Searching for Governor 2026 candidates...")
    data = urllib.parse.urlencode({
        "searchType": "candidate",
        "name": "",
        "officeSelection": OFFICE_ID,
        "districtSelection": "",
        "electionYearSelection": ELECTION_YEAR_ID,
        "partySelection": "",
        "nameField": "true",
        "partyField": "true",
        "officeField": "true",
        "electionYearField": "true",
        "_continue": "Continue",
    }).encode()

    req = urllib.request.Request(SEARCH_URL, data=data,
        headers={"Referer": SEARCH_URL, "Content-Type": "application/x-www-form-urlencoded"})
    resp = opener.open(req)
    html = resp.read().decode()

    # Extract candidate IDs and names
    candidates = re.findall(r'replist\.htm\?id=(\d+)&owner=([^"]+)"', html)
    # Also extract party from the table
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)

    results = []
    for cid, raw_name in candidates:
        name = urllib.parse.unquote(raw_name).strip()
        info = NAME_MAP.get(name, {"name": name, "party": "unknown"})
        results.append({
            "id": cid,
            "raw_name": name,
            "name": info["name"],
            "party": info["party"],
        })

    print(f"[Finance] Found {len(results)} candidates")
    return results


def get_report_list(opener, candidate):
    """Get list of filed reports for a candidate."""
    cid = candidate["id"]
    name = urllib.parse.quote(candidate["raw_name"])
    url = f"{BASE_URL}/public/replist.htm?id={cid}&owner={name}"

    try:
        resp = opener.open(url, timeout=30)
        html = resp.read().decode()
    except Exception as e:
        print(f"  [!] Error getting report list for {candidate['name']}: {e}")
        return []

    # Extract report IDs and metadata
    reports = []
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        report_match = re.search(r'report_full\.htm\?reportId=(\d+)', row)
        if report_match:
            rid = report_match.group(1)
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            reports.append({
                "reportId": rid,
                "year": clean[0] if len(clean) > 0 else "",
                "type": clean[1] if len(clean) > 1 else "",
                "filed": clean[3] if len(clean) > 3 else "",
            })

    return reports


def parse_dollar(s):
    """Parse dollar string like '$5,357,822.23' to float."""
    if not s or s == '?':
        return 0.0
    cleaned = s.replace('$', '').replace(',', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def get_report_summary(opener, report_id):
    """Extract financial summary from a report."""
    url = f"{REPORT_URL}?reportId={report_id}"
    try:
        resp = opener.open(url, timeout=60)
        html = resp.read().decode()
    except Exception as e:
        print(f"  [!] Error fetching report {report_id}: {e}")
        return None

    summary = {}
    labels = [
        ("beginningBalance", "Beginning Balance"),
        ("totalContributions", "TOTAL CONTRIBUTIONS"),
        ("totalReceipts", "TOTAL RECEIPTS"),
        ("totalDisbursements", "TOTAL DISBURSEMENTS"),
        ("totalObligations", "TOTAL OBLIGATIONS"),
        ("endingBalance", "Ending Balance"),
        ("unitemizedContributions", "Monetary Contributions, Unitemized"),
        ("loansReceived", "Loans Received"),
        ("loansMade", "Loans Made"),
    ]

    for key, label in labels:
        idx = html.find(label)
        if idx > -1:
            chunk = re.sub(r'<[^>]+>', ' ', html[idx:idx+500])
            amounts = re.findall(r'\$[\d,]+\.\d{2}', chunk)
            if amounts:
                summary[key] = parse_dollar(amounts[0])

    # Also try to count contributions
    contrib_count = len(re.findall(r'Rec\'d For.*?Primary|Rec\'d For.*?General', html))
    if contrib_count > 0:
        summary["contributionCount"] = contrib_count

    return summary


def load_current_finance():
    """Load existing finance data for merging."""
    for path in [FINANCE_FILE, MAIN_FINANCE]:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except Exception:
                continue
    return {"candidates": []}


def scrape_all():
    """Main scrape function."""
    print("=" * 60)
    print("[Finance] Starting campaign finance scrape")
    print(f"[Finance] Source: {BASE_URL}")
    print("=" * 60)

    opener = create_opener()
    get_session(opener)
    candidates = search_candidates(opener)

    if not candidates:
        print("[Finance] ERROR: No candidates found!")
        return None

    # Load existing data to preserve manual fields
    existing = load_current_finance()
    existing_by_name = {}
    for c in existing.get("candidates", []):
        existing_by_name[c["name"]] = c

    scraped_candidates = []
    for cand in candidates:
        print(f"\n[Finance] Processing: {cand['name']} ({cand['party'].upper()})")
        time.sleep(0.5)  # Be polite

        reports = get_report_list(opener, cand)
        if not reports:
            print(f"  No reports filed")
            scraped_candidates.append({
                "name": cand["name"],
                "party": cand["party"],
                "totalRaised": 0,
                "totalSpent": 0,
                "cashOnHand": 0,
                "loansReceived": 0,
                "reportsFiled": 0,
                "lastReportDate": None,
                "lastReportType": None,
            })
            continue

        print(f"  Found {len(reports)} report(s)")
        latest = reports[0]  # Most recent
        print(f"  Latest: {latest['type']} (filed {latest['filed']})")

        time.sleep(0.5)
        summary = get_report_summary(opener, latest["reportId"])
        if not summary:
            print(f"  ERROR: Could not parse report")
            continue

        raised = summary.get("totalContributions", 0)
        spent = summary.get("totalDisbursements", 0)
        coh = summary.get("endingBalance", 0)
        loans = summary.get("loansReceived", 0)

        print(f"  Raised: ${raised:,.2f} | Spent: ${spent:,.2f} | COH: ${coh:,.2f}")
        if loans > 0:
            print(f"  Loans: ${loans:,.2f}")

        entry = {
            "name": cand["name"],
            "party": cand["party"],
            "totalRaised": round(raised, 2),
            "totalSpent": round(spent, 2),
            "cashOnHand": round(coh, 2),
            "loansReceived": round(loans, 2),
            "warChest": round(raised + loans, 2),
            "reportsFiled": len(reports),
            "lastReportDate": latest["filed"],
            "lastReportType": latest["type"],
        }

        # Preserve manual fields from existing data
        old = existing_by_name.get(cand["name"], {})
        for field in ["personalLoans", "inStatePct", "outStatePct",
                      "contributionCount", "highlights"]:
            if field in old:
                entry[field] = old[field]

        # Use scraped loan data if we got it and it's nonzero
        if loans > 0 and "personalLoans" not in entry:
            entry["personalLoans"] = round(loans, 2)

        scraped_candidates.append(entry)
        time.sleep(0.5)

    # Sort: by total raised descending
    scraped_candidates.sort(key=lambda c: c.get("totalRaised", 0), reverse=True)

    # Build output
    now = datetime.now(timezone.utc)
    output = {
        "lastUpdated": now.strftime("%Y-%m-%d"),
        "lastScraped": now.isoformat(),
        "reportingPeriod": existing.get("reportingPeriod", ""),
        "source": "Tennessee Registry of Election Finance",
        "sourceUrl": "https://apps.tn.gov/tncamp/public/cpsearch.htm",
        "candidates": scraped_candidates,
        "analysis": existing.get("analysis", ""),
    }

    return output


def run():
    """Entry point for run_all.py integration."""
    try:
        result = scrape_all()
        if result and result["candidates"]:
            SCRAPED_DIR.mkdir(parents=True, exist_ok=True)
            with open(FINANCE_FILE, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n[Finance] OK - Wrote {len(result['candidates'])} candidates to {FINANCE_FILE}")
            return True
        else:
            print("[Finance] FAIL - No data scraped")
            return False
    except Exception as e:
        print(f"[Finance] FAIL - Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run()
    if not success:
        exit(1)
