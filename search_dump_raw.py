with open("all_edits_dump.txt", "r", encoding="utf-8") as f:
    text = f.read()

import re
# Find all occurrences of "[number] Conv:"
matches = re.finditer(r"\[\d+\] Conv:[^\n]+", text)
matches = list(matches)

print(f"Total matches found: {len(matches)}")
for idx, match in enumerate(matches):
    start = match.start()
    end = matches[idx+1].start() if idx+1 < len(matches) else len(text)
    section = text[start:end]
    
    header = match.group(0)
    print(f"\nEdit {idx}: {header}")
    # Print the tool and first few lines of section
    lines = section.split("\n")
    for l in lines[1:8]:
        if l.strip():
            print("  " + l)
