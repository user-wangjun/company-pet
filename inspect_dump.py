with open("all_edits_dump.txt", "r", encoding="utf-8") as f:
    content = f.read()

import re
entries = content.split("========================================================")
print(f"Total entries: {len(entries)}")

for i, entry in enumerate(entries):
    if not entry.strip():
        continue
    # print headers
    lines = entry.strip().split("\n")
    header = lines[0]
    print(f"\nEntry {i}: {header}")
    for l in lines[1:10]:
        print("  " + l)
