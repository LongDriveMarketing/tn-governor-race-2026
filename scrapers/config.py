# TNFirefly Governor Race Tracker - Scraper Configuration
# =====================================================

import os

# GitHub repo settings
GITHUB_REPO = "LongDriveMarketing/tn-governor-race-2026"
GITHUB_BRANCH = "main"
DATA_DIR = "data"

# =============================================================
# NEWS SOURCES
# =============================================================

# RSS feeds to scrape for governor race news
NEWS_RSS_FEEDS = [
    # --- TNFirefly (our own content — looser filter) ---
    {
        "name": "Tennessee Firefly",
        "url": "https://www.tnfirefly.com/news?format=rss",
        "source_key": "Tennessee Firefly",
        "tier": "tnfirefly"
    },
    # --- National / Unbiased ---
    {
        "name": "Associated Press",
        "url": "https://rsshub.app/apnews/topics/tennessee",
        "source_key": "Associated Press",
        "tier": "national"
    },
    {
        "name": "Reuters - US Politics",
        "url": "https://www.reutersagency.com/feed/?best-topics=political-general",
        "source_key": "Reuters",
        "tier": "national"
    },
    # --- National / Conservative ---
    {
        "name": "Fox News - Politics",
        "url": "https://moxie.foxnews.com/google-publisher/politics.xml",
        "source_key": "Fox News",
        "tier": "national"
    },
    # --- National / Political ---
    {
        "name": "The Hill",
        "url": "https://thehill.com/feed/",
        "source_key": "The Hill",
        "tier": "national"
    },
]

# =============================================================
# CANDIDATE CAMPAIGN SOURCES
# =============================================================

# Campaign websites with news/press pages to scrape
CAMPAIGN_WEBSITES = [
    {
        "name": "Rose Campaign",
        "url": "https://johnrose.com/news/",
        "source_key": "Rose Campaign",
        "candidate": "Rose",
        "party": "rep"
    },
    {
        "name": "Blackburn Campaign",
        "url": "https://marshablackburn.com/",
        "source_key": "Blackburn Campaign",
        "candidate": "Blackburn",
        "party": "rep"
    },
    {
        "name": "Green Campaign",
        "url": "https://greenforgovernor.com/",
        "source_key": "Green Campaign",
        "candidate": "Green",
        "party": "dem"
    },
]

# Candidate X (Twitter) accounts — scraped via RSSHub bridge
CANDIDATE_X_FEEDS = [
    {
        "name": "Blackburn X",
        "handle": "VoteMarsha",
        "source_key": "Blackburn (X)",
        "candidate": "Blackburn",
        "party": "rep"
    },
    {
        "name": "Rose X",
        "handle": "JohnRoseforTN",
        "source_key": "Rose (X)",
        "candidate": "Rose",
        "party": "rep"
    },
    {
        "name": "Green X",
        "handle": "Jerri_M_Green",
        "source_key": "Green (X)",
        "candidate": "Green",
        "party": "dem"
    },
    {
        "name": "Fritts X",
        "handle": "MontyFritts4TN",
        "source_key": "Fritts (X)",
        "candidate": "Fritts",
        "party": "rep"
    },
]

# RSSHub bridge URL for converting X feeds to RSS
# Falls back if primary is down
RSSHUB_INSTANCES = [
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
    "https://rsshub.moeyy.cn",
]

# =============================================================
# POLLING SOURCES
# =============================================================

POLLING_SOURCES = [
    {
        "name": "Beacon Center / TennSight",
        "type": "primary",
        "frequency": "quarterly",
        "sample_size": 1200,
        "margin": 2.77,
        "urls": {
            "polls_index": "https://tennsight.com/polls/",
            "latest_poll": "https://tennsight.com/polls/january-2026/",
            "elections": "https://tennsight.com/elections/",
        },
        "rss": "https://tennsight.com/feed/"
    },
    {
        "name": "Vanderbilt Poll",
        "type": "primary",
        "frequency": "semiannual",
        "sample_size": 1000,
        "urls": {
            "home": "https://www.vanderbilt.edu/csdi/vupoll-home.php",
            "news": "https://news.vanderbilt.edu/?s=vanderbilt+poll",
        },
        "rss": None
    },
    {
        "name": "MTSU Poll",
        "type": "secondary",
        "frequency": "periodic",
        "sample_size": 600,
        "margin": 4.0,
        "urls": {
            "home": "http://mtsupoll.org/",
        },
        "rss": None
    },
    {
        "name": "RealClearPolling",
        "type": "aggregator",
        "urls": {
            "tn_gov_rep": "https://www.realclearpolling.com/polls/governor/republican-primary/2026/tennessee",
            "tn_gov_general": "https://www.realclearpolling.com/polls/governor/general/2026/tennessee",
        }
    },
    {
        "name": "270toWin",
        "type": "aggregator",
        "urls": {
            "tn_gov": "https://www.270towin.com/2026-governor-polls/tennessee",
        }
    },
    {
        "name": "Ballotpedia",
        "type": "reference",
        "urls": {
            "race": "https://ballotpedia.org/Tennessee_gubernatorial_election,_2026",
        }
    },
]

# Legacy variables used by scrape_polls.py
POLLING_URLS = [
    "https://www.270towin.com/2026-governor-polls/tennessee",
    "https://www.realclearpolling.com/polls/governor/general/2026/tennessee",
    "https://www.realclearpolling.com/polls/governor/republican-primary/2026/tennessee",
]

TENNSIGHT_URLS = {
    "elections": "https://tennsight.com/elections/",
    "polls_index": "https://tennsight.com/polls/",
    "latest_poll": "https://tennsight.com/polls/january-2026/",
}

# TN Secretary of State
SOS_CANDIDATE_URL = "https://sos.tn.gov/elections/2026-candidate-lists"
SOS_FINANCE_URL = "https://apps.tn.gov/tncamp/public/cpsearch.htm"

# =============================================================
# KEYWORD MATCHING
# =============================================================

# Keywords to match governor race articles (case-insensitive)
GOVERNOR_KEYWORDS = [
    "governor", "gubernatorial", "governor's race",
    "blackburn", "marsha blackburn",
    "john rose", "rose campaign",
    "monty fritts", "fritts",
    "jerri green", "green campaign",
    "carnita atwater", "atwater",
    "adam kurtz", "ditch kurtz",
    "cito pellegra",
    "tennessee governor", "tn governor",
    "filing deadline", "qualifying petition",
    "primary election 2026", "general election 2026",
    "tennessee primary", "volunteer state governor"
]

# Candidate detection patterns → party assignment
CANDIDATE_PATTERNS = {
    "blackburn": {"party": "rep", "candidate": "Blackburn"},
    "marsha blackburn": {"party": "rep", "candidate": "Blackburn"},
    "john rose": {"party": "rep", "candidate": "Rose"},
    "rose campaign": {"party": "rep", "candidate": "Rose"},
    "monty fritts": {"party": "rep", "candidate": "Fritts"},
    "fritts": {"party": "rep", "candidate": "Fritts"},
    "pellegra": {"party": "rep", "candidate": "Pellegra"},
    "jerri green": {"party": "dem", "candidate": "Green"},
    "carnita atwater": {"party": "dem", "candidate": "Atwater"},
    "adam kurtz": {"party": "dem", "candidate": "Kurtz"},
    "ditch kurtz": {"party": "dem", "candidate": "Kurtz"},
    "tim cyr": {"party": "dem", "candidate": "Cyr"},
    "stephen maxwell": {"party": "ind", "candidate": "Maxwell"}
}

# Tag auto-detection keywords
TAG_KEYWORDS = {
    "finance": ["fundrais", "finance", "donor", "raised", "war chest", "money", "campaign fund", "contribution"],
    "policy": ["voucher", "education", "school", "teacher", "curriculum", "testing", "literacy", "medicaid", "healthcare"],
    "campaign": ["announce", "launch", "enter", "file", "candidacy", "campaign trail", "rally", "endorsement"],
    "controversy": ["controversy", "scandal", "viral", "backlash", "criticism", "outrage"],
    "analysis": ["poll", "survey", "rating", "forecast", "analysis", "polling"],
    "podcast": ["podcast", "on the fly", "episode", "interview"]
}
