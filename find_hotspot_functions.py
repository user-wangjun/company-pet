with open("all_edits_dump.txt", "r", encoding="utf-8") as f:
    text = f.read()

import re

# We want to find sections containing "activateHotspot"
matches = re.finditer(r"\[\d+\] Conv:[^\n]+", text)
matches = list(matches)

for idx, match in enumerate(matches):
    start = match.start()
    end = matches[idx+1].start() if idx+1 < len(matches) else len(text)
    section = text[start:end]
    
    if "activateHotspot" in section and "StartLine" in section:
        # Let's save the section to a file
        fn = f"activate_hotspot_section_{idx}.txt"
        with open(fn, "w", encoding="utf-8") as out:
            out.write(section)
        print(f"Saved match {idx} containing activateHotspot to {fn}")
