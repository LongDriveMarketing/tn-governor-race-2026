import json
data = json.load(open(r"C:\Users\gardn\OneDrive\Desktop\Claude Code Blocks\TNFIREFLY\tn-governor-race-2026\data\news.json"))

drop_sources = ["The Tennessean", "Tennessee Lookout", "Memphis Commercial Appeal",
                "Nashville Scene", "Axios Nashville", "Johnson City Press"]
keep_sources = ["Beacon Center / TennSight", "Beacon Center of Tennessee",
                "Tennessee Firefly", "Associated Press", "Right Wing Watch",
                "TN Secretary of State"]

print("=== WOULD REMOVE ===")
for a in data["articles"]:
    if a["source"] in drop_sources:
        url_status = "HAS URL" if a.get("url") else "NO URL (manual)"
        print(f"  [{a['source']}] {url_status} | {a['title'][:65]}")

print("\n=== WOULD KEEP ===")
for a in data["articles"]:
    if a["source"] in keep_sources:
        print(f"  [{a['source']}] {a['title'][:65]}")

# Also check scraped articles (have URLs to TN outlets)
print("\n=== SCRAPED FROM TN OUTLETS (have URLs) ===")
tn_domains = ["tennesseelookout.com", "tennessean.com", "axios.com/local/nashville",
              "johnsoncitypress.com", "nashvillescene.com", "commercialappeal.com"]
for a in data["articles"]:
    url = a.get("url", "")
    if any(d in url for d in tn_domains):
        print(f"  [{a['source']}] {a['url'][:70]}")
