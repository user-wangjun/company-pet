import json
import os

brain_dir = r"C:\Users\13640\.gemini\antigravity\brain"
matches = []

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file == "transcript.jsonl":
            tf = os.path.join(root, file)
            parts = tf.split(os.sep)
            try:
                idx = parts.index("brain")
                conv_id = parts[idx + 1]
            except:
                conv_id = "unknown"
            
            with open(tf, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if "activateHotspot" in line:
                        matches.append((conv_id, file, i, line))

print(f"Found {len(matches)} matches.")
for conv_id, fn, i, line in matches:
    print(f"\nConv: {conv_id}, Line {i}")
    # Print the line or part of it
    if len(line) < 500:
        print(line)
    else:
        # Let's search where "activateHotspot" is in the line
        idx = line.find("activateHotspot")
        start = max(0, idx - 200)
        end = min(len(line), idx + 1000)
        print(f"...{line[start:end]}...")
