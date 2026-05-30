import json
import os

brain_dir = r"C:\Users\13640\.gemini\antigravity\brain"
matches = []

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file == "transcript.jsonl":
            tf = os.path.join(root, file)
            with open(tf, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if "App.tsx" in line and ("isMarketingRoute" in line or "MarketingPage" in line):
                        matches.append((tf, i, line))

print(f"Found {len(matches)} matches.")
for tf, i, line in matches[:10]:
    print(f"\nFile: {tf}, Line {i}")
    # print around 300 chars of match
    idx = line.find("App.tsx")
    start = max(0, idx - 100)
    end = min(len(line), idx + 800)
    print(f"...{line[start:end]}...")
