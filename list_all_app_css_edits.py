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
                    if "app.css" in line.lower():
                        try:
                            data = json.loads(line)
                            if "tool_calls" in data:
                                for tc in data["tool_calls"]:
                                    args = tc.get("args", {})
                                    if isinstance(args, str):
                                        args = json.loads(args)
                                    target_file = args.get("TargetFile", args.get("targetFile", ""))
                                    if "app.css" in target_file.lower():
                                        matches.append((conv_id, i, tc.get("name"), args))
                        except Exception:
                            pass

print(f"Found {len(matches)} total edits targeting App.css.")
# Let's sort them by conv_id and line
matches.sort(key=lambda x: x[0] + f"{x[1]:05d}")
for idx, (conv_id, i, name, args) in enumerate(matches):
    print(f"  [{idx}] Conv: {conv_id}, Line: {i}, Tool: {name}, Instruction: {args.get('Instruction')}")
