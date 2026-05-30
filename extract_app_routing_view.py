import json
import os

log_path = r"C:\Users\13640\.gemini\antigravity\brain\825746b1-43a3-44cc-a2d8-a4112f973005\.system_generated\logs\transcript.jsonl"

with open(log_path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i == 46:
            data = json.loads(line)
            content = data.get("content", "")
            with open("app_final_lines.txt", "w", encoding="utf-8") as out:
                out.write(content)
            print("Successfully wrote transcript line 46 content to app_final_lines.txt")
            break
