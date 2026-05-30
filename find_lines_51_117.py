with open("all_edits_dump.txt", "r", encoding="utf-8") as f:
    text = f.read()

import re

# We want to find sections containing "hotspotTimerRef" and print them
matches = re.finditer(r"\[\d+\] Conv:[^\n]+", text)
matches = list(matches)

for idx, match in enumerate(matches):
    start = match.start()
    end = matches[idx+1].start() if idx+1 < len(matches) else len(text)
    section = text[start:end]
    
    if "hotspotTimerRef" in section or "activateHotspot" in section or "handlePointerMove" in section:
        print(f"\n========================================================")
        print(f"Match {idx}: {match.group(0)}")
        print(f"========================================================")
        # print the section in full (or look for where the replacement content is)
        print(section[:2000]) # Print first 2000 chars of section
        if len(section) > 2000:
            print("... [TRUNCATED IN SCRIPT OUTPUT, let's write to a separate file] ...")
            fn = f"matching_section_{idx}.txt"
            with open(fn, "w", encoding="utf-8") as out:
                out.write(section)
            print(f"Saved full section to {fn}")
