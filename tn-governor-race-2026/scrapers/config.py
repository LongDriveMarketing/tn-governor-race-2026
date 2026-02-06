# TNFirefly Governor Race Tracker - Scraper Configuration
# =====================================================

import os

# GitHub repo settings
GITHUB_REPO = "LongDriveMarketing/tn-governor-race-2026"
GITHUB_BRANCH = "main"
DATA_DIR = "data"

# RSS feeds to scrape for governor race news
NEWS_RSS_FEEDS = [
    {
        "name": "Tennessee Lookout",
        "url": "https://tennesseelookout.com/feed/",
        "source_key": "Tennessee Lookout"
    },
    {
        "name": "The Tennessean",
        "url": "https://www.tennessean.com/arcio/rss/category/news/politics/state-government/",
        "source_key": "The Tennessean"
    },
    {
        "name": "Axios Nashville",
        "url": "https://www.axios.com/local/nashville/feed",
        "source_key": "Axios Nashville"
    },
    {
        "name": "Associated Press - TN",
        "url": "https://rsshub.app/apnews/topics/tennessee",
        "source_key": "Associated Press"
    },
    {
        "name": "TennSight / Beacon Center",
        "url": "https://tennsight.com/feed/",
        "source_key": "Beacon Center / TennSight"
    }
]

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
    "filing deadline", "qualifying petition",
    "primary election 2026", "general election 2026"
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

# Polling sources
POLLING_URLS = [
    "https://www.270towin.com/2026-governor-polls/tennessee",
    "https://ballotpedia.org/Tennessee_gubernatorial_election,_2026"
]

# Beacon Center / TennSight — primary polling source for TN governor race
# They poll quarterly (Jan, Apr, Aug, Nov) with 1,200 RV, ±2.77% MOE
TENNSIGHT_URLS = {
    "elections": "https://tennsight.com/elections/",
    "education": "https://tennsight.com/education/",
    "latest_poll": "https://tennsight.com/polls/january-2026/",
    "polls_index": "https://tennsight.com/polls/",
    "poll_pattern": "https://tennsight.com/polls/{slug}/"
}

# TN Secretary of State
SOS_CANDIDATE_URL = "https://sos.tn.gov/elections/2026-candidate-lists"
SOS_FINANCE_URL = "https://apps.tn.gov/tncamp/public/cpsearch.htm"

# Tag auto-detection keywords
TAG_KEYWORDS = {
    "finance": ["fundrais", "finance", "donor", "raised", "war chest", "money", "campaign fund", "contribution"],
    "policy": ["voucher", "education", "school", "teacher", "curriculum", "testing", "literacy"],
    "campaign": ["announce", "launch", "enter", "file", "candidacy", "campaign trail"],
    "controversy": ["controversy", "scandal", "viral", "backlash", "criticism"],
    "analysis": ["poll", "survey", "rating", "forecast", "analysis"]
}
