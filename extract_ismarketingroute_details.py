import json
import os

brain_dir = r"C:\Users\13640\.gemini\antigravity\brain"
matches = []

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file == "transcript.jsonl":
            tf = os.path.join(root, file)
            with open(tf, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if "isMarketingRoute" in line:
                        try:
                            data = json.loads(line)
                            if "tool_calls" in data:
                                for tc in data["tool_calls"]:
                                    if tc.get("name") in ("replace_file_content", "multi_replace_file_content"):
                                        args = tc.get("args", {})
                                        if isinstance(args, str):
                                            args = json.loads(args)
                                        target_file = args.get("TargetFile", args.get("targetFile", ""))
                                        # Let's save the match if it targets App.tsx or main.tsx or similar
                                        matches.append((tf, i, tc.get("name"), target_file, args))
                        except Exception:
                            pass

print(f"Found {len(matches)} tool call matches.")
for idx, (tf, i, name, target, args) in enumerate(matches):
    print(f"\n[{idx}] File: {tf}, Line: {i}, Tool: {name}, Target: {target}")
    fn = f"ismarketingroute_edit_{idx}.txt"
    with open(fn, "w", encoding="utf-8") as out:
        out.write(json.dumps(args, indent=2, ensure_ascii=False))
    print(f"  Saved to {fn}")
