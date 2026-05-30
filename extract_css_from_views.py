import json
import os
import re

brain_dir = r"C:\Users\13640\.gemini\antigravity\brain"
line_pattern = re.compile(r"^\s*(\d+):\s(.*)$")

all_css_lines = {}

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file == "transcript.jsonl":
            tf = os.path.join(root, file)
            with open(tf, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if "app.css" in line.lower() and "showing lines" in line.lower():
                        try:
                            data = json.loads(line)
                            content = data.get("content", "")
                            lines = content.split("\n")
                            for l in lines:
                                m = line_pattern.match(l)
                                if m:
                                    line_num = int(m.group(1))
                                    line_content = m.group(2)
                                    all_css_lines[line_num] = line_content
                        except Exception:
                            pass

print(f"Extracted {len(all_css_lines)} lines of App.css from all historical view logs.")
# Let's write them out sorted by line number
sorted_keys = sorted(all_css_lines.keys())
print(f"Line range: {sorted_keys[0]} to {sorted_keys[-1]} (Total unique lines: {len(sorted_keys)})")

# Let's write the entire App.css to a file!
with open("reconstructed_App_historic.css", "w", encoding="utf-8") as out:
    for k in sorted_keys:
        out.write(all_css_lines[k] + "\n")
print("Saved reconstructed App.css to reconstructed_App_historic.css")
