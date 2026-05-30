import json
import os

brain_dir = r"C:\Users\13640\.gemini\antigravity\brain"
css_edits = []

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
                    if "app.css" in line.lower() and "replace_file_content" in line:
                        try:
                            data = json.loads(line)
                            if "tool_calls" in data:
                                for tc in data["tool_calls"]:
                                    args = tc.get("args", {})
                                    if isinstance(args, str):
                                        args = json.loads(args)
                                    target_file = args.get("TargetFile", args.get("targetFile", ""))
                                    if "app.css" in target_file.lower():
                                        css_edits.append((conv_id, i, args))
                        except Exception:
                            pass

print(f"Found {len(css_edits)} edits to App.css.")
for idx, (conv_id, i, args) in enumerate(css_edits):
    fn = f"css_edit_{conv_id}_{i}.txt"
    with open(fn, "w", encoding="utf-8") as out:
        out.write(json.dumps(args, indent=2, ensure_ascii=False))
    print(f"  [{idx}] Saved Conv {conv_id} Line {i} to {fn}")
