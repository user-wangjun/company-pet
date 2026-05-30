with open("all_edits_dump.txt", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = list(re.finditer(r"\[\d+\] Conv:[^\n]+", text))
print(f"Found {len(matches)} matches.")

for idx, match in enumerate(matches):
    start = match.start()
    end = matches[idx+1].start() if idx+1 < len(matches) else len(text)
    section = text[start:end]
    
    fn = f"edit_{idx}.txt"
    with open(fn, "w", encoding="utf-8") as out:
        out.write(section)
    print(f"Saved edit {idx} to {fn}")
