with open("all_edits_dump.txt", "r", encoding="utf-8") as f:
    content = f.read()

import re
entries = content.split("========================================================")

for i, entry in enumerate(entries):
    if "Tool: write_to_file" in entry and "MarketingPage.tsx" in entry:
        print(f"Entry {i} is write_to_file of MarketingPage.tsx")
        # Let's save the entry to a separate file
        with open(f"write_to_file_entry_{i}.txt", "w", encoding="utf-8") as out:
            out.write(entry)
        print(f"  Saved entry {i} to write_to_file_entry_{i}.txt")
