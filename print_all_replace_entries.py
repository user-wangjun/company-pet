with open("all_edits_dump.txt", "r", encoding="utf-8") as f:
    content = f.read()

entries = content.split("========================================================")

for i, entry in enumerate(entries):
    if not entry.strip():
        continue
    lines = entry.strip().split("\n")
    header = lines[0]
    if "replace_file_content" in header and "MarketingPage.tsx" in header:
        print(f"Entry {i}: {header}")
        # Find StartLine, EndLine, ReplacementContent length
        start_line = None
        end_line = None
        repl_len = 0
        for l in lines:
            if "StartLine:" in l:
                start_line = l
            if "EndLine:" in l:
                end_line = l
            if "ReplacementContent" in l:
                # find index of ReplacementContent
                idx = entry.find("ReplacementContent:")
                if idx != -1:
                    repl_len = len(entry[idx + len("ReplacementContent:"):].strip())
                    break
        print(f"  {start_line}, {end_line}, ReplacementContent length: {repl_len}")
