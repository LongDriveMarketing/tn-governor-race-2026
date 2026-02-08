import json

path = r"C:\Users\gardn\OneDrive\Desktop\Claude Code Blocks\TNFIREFLY\tn-governor-race-2026\data\news.json"
data = json.load(open(path))

drop_sources = ["The Tennessean", "Tennessee Lookout", "Memphis Commercial Appeal",
                "Nashville Scene", "Axios Nashville", "Johnson City Press"]

changed = 0
for a in data["articles"]:
    if a["source"] in drop_sources:
        old = a["source"]
        a["source"] = "Tennessee Firefly"
        a["tnfirefly"] = True
        changed += 1
        print(f"  Re-attributed: [{old}] -> [Tennessee Firefly] | {a['title'][:55]}")

# Also remove the old Beacon duplicate if it exists
dupes = set()
cleaned = []
for a in data["articles"]:
    if a["id"] not in dupes:
        cleaned.append(a)
        dupes.add(a["id"])

data["articles"] = cleaned
data["lastUpdated"] = "2026-02-08"

with open(path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nDone! Re-attributed {changed} articles. Total: {len(cleaned)}")
