with open("all_edits_dump.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "activateHotspot" in line:
        print(f"--- MATCH AT LINE {i} ---")
        start = max(0, i - 15)
        end = min(len(lines), i + 25)
        for j in range(start, end):
            print(f"{j:4d}: {lines[j]}", end="")
