import os
import json
import re

brain_dir = r"C:\Users\13640\.gemini\antigravity\brain"

line_pattern = re.compile(r"^\s*(\d+):\s(.*)$")
marketing_page_lines = {}

all_steps = []
for conv_id in os.listdir(brain_dir):
    log_path = os.path.join(brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
    if not os.path.exists(log_path):
        continue
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                obj = json.loads(line)
                t = obj.get("type", "")
                content = obj.get("content", "")
                if t == "VIEW_FILE" and content:
                    lines = content.split("\n")
                    filepath = ""
                    for l in lines:
                        if "File Path:" in l:
                            filepath = l.split("File Path:")[-1].strip(" `").lower()
                    if filepath and "marketingpage.tsx" in filepath:
                        all_steps.append((obj.get("created_at", ""), lines))
            except Exception:
                pass

all_steps.sort(key=lambda x: x[0])
for created_at, lines in all_steps:
    for l in lines:
        m = line_pattern.match(l)
        if m:
            line_num = int(m.group(1))
            line_content = m.group(2)
            marketing_page_lines[line_num] = line_content

missing = []
for i in range(1, max(marketing_page_lines.keys()) + 1):
    if i not in marketing_page_lines:
        missing.append(i)
print("MISSING LINES:", missing)
