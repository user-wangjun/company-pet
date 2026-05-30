import json
import os

log_path = r"C:\Users\13640\.gemini\antigravity\brain\12d163ea-518d-4922-a90e-d5f1401faf15\.system_generated\logs\transcript.jsonl"

with open(log_path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i == 152:
            data = json.loads(line)
            content = data.get("content", "")
            with open("extracted_lines_50_90.txt", "w", encoding="utf-8") as out:
                out.write(content)
            print("Successfully wrote transcript line 152 content to extracted_lines_50_90.txt")
            break
